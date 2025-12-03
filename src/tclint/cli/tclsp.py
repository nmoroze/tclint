import argparse
import dataclasses
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import uuid

from lsprotocol import types as lsp

from pygls.server import LanguageServer
from pygls.workspace import TextDocument
from pygls.uris import to_fs_path

from tclint.cli import tclint
from tclint.config import (
    DEFAULT_CONFIGS,
    RunConfig,
    Config,
    ConfigError,
    load_config_at,
)
from tclint.format import Formatter, FormatterOpts
from tclint.lexer import TclSyntaxError
from tclint.parser import Parser
from tclint.cli import utils

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"


DIAGNOSTIC_SOURCE = "tclint"
_DEFAULT_CONFIG = Config()


def lint(source, config, path):
    diagnostics = []

    try:
        violations = tclint.lint(source, config, path)
    except TclSyntaxError as e:
        return [
            lsp.Diagnostic(
                message=str(e),
                severity=lsp.DiagnosticSeverity.Error,
                range=lsp.Range(
                    start=lsp.Position(e.start[0] - 1, e.start[1] - 1),
                    end=lsp.Position(e.end[0] - 1, e.end[1] - 1),
                ),
                code="syntax error",
                source=DIAGNOSTIC_SOURCE,
            )
        ]

    for violation in violations:
        message = violation.message
        severity = lsp.DiagnosticSeverity.Warning
        start = lsp.Position(
            line=violation.start[0] - 1, character=violation.start[1] - 1
        )
        end = lsp.Position(line=violation.end[0] - 1, character=violation.end[1] - 1)

        diagnostics.append(
            lsp.Diagnostic(
                message=message,
                severity=severity,
                range=lsp.Range(
                    start=start,
                    end=end,
                ),
                code=violation.id,
                source=DIAGNOSTIC_SOURCE,
            )
        )

    return diagnostics


@dataclasses.dataclass
class ExtensionSettings:
    # This path is expected to be absolute.
    config_file: Optional[Path] = dataclasses.field(default=None)


class TclspServer(LanguageServer):
    """Main server class. Implements pull diagnostics using a method adapted from
    https://pygls.readthedocs.io/en/latest/examples/pull-diagnostics.html."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = {}

        # There are many config caches!!
        # Caches loaded config files specified in LSP settings.
        self.workspace_configs: Dict[Path, Config] = {}
        # Caches loaded config files present in open workspaces.
        self.config_files: Dict[Path, Config] = {}
        # Caches which config is used by each open file.
        self.source_configs: Dict[Path, Config] = {}
        # Tracks which invalid configs we've already displayed an error for, to avoid
        # spam.
        self.invalid_configs: Set[Path] = set()

        self.client_supports_refresh = False

        self.global_settings = ExtensionSettings()
        self.workspace_settings: Dict[Path, ExtensionSettings] = {}

    def get_roots(self) -> List[Path]:
        """Returns root folders currently open in the workspace."""
        roots = []
        for uri in self.workspace.folders.keys():
            path = to_fs_path(uri)
            if path is not None:
                roots.append(Path(path))

        if len(roots) > 0:
            return roots

        if self.workspace.root_path is not None:
            roots.append(Path(self.workspace.root_path))

        return roots

    def get_root(self, path: Path) -> Optional[Path]:
        """Returns workspace root if path is in a workspace folder. Otherwise, returns
        None.
        """
        roots = self.get_roots()
        closest_root = None
        distance = float("inf")
        for root in roots:
            try:
                relpath = path.relative_to(root)
            except ValueError:
                continue
            if len(relpath.parts) < distance:
                distance = len(relpath.parts)
                closest_root = root

        return closest_root

    def get_config_file(self, root: Path) -> Optional[Path]:
        if root in self.workspace_settings:
            settings = self.workspace_settings[root]
            return settings.config_file
        return self.global_settings.config_file

    def show_config_error(self, msg: str, path: Path):
        if path not in self.invalid_configs:
            self.show_message(f"Error loading config file: {msg}")
        self.invalid_configs.add(path)

    def load_config(self, path: Path, root: Path) -> Optional[Config]:
        try:
            return RunConfig.from_path(path, root)._global_config
        except FileNotFoundError:
            self.show_config_error(f"{path} doesn't exist", path)
            return None
        except ConfigError as e:
            self.show_config_error(str(e), path)
            return None

    def load_workspace_setting_configs(self):
        """These may be used a lot if specified, so cache specially."""
        for root in self.get_roots():
            path = self.get_config_file(root)
            if path is None:
                continue
            config = self.load_config(path, root)
            if config is None:
                continue
            self.workspace_configs[root] = config

    def _get_config(self, path: Path) -> Config:
        workspace_root = self.get_root(path)

        # First, check for configs specified in the LSP settings.
        # If not in a workspace, our only shot is to use a global config. Otherwise, we
        # bail (no searching, since the LSP only searches up to the workspace root).
        if workspace_root is None:
            global_file = self.global_settings.config_file
            if global_file is not None:
                config = self.load_config(global_file, path.parent)
                if config is not None:
                    return config
            return _DEFAULT_CONFIG

        # If file is in a workspace, and we've got a workspace config configured, use
        # that (this logic also handles global configs, since these are still
        # instantiated once per workspace to resolve relative paths).
        if workspace_root is not None and workspace_root in self.workspace_configs:
            return self.workspace_configs[workspace_root]

        # Otherwise, walk upwards until root.
        # path is a file, which is a sneaky trick to guarantee we always run the first
        # iteration. It becomes a directory after the first statement in the loop.
        while path != workspace_root:
            path = path.parent
            try:
                config = load_config_at(path)
            except ConfigError as e:
                self.show_config_error(str(e), path)
                return _DEFAULT_CONFIG

            if config is not None:
                return config

        return _DEFAULT_CONFIG

    def get_config(self, path: Path) -> Config:
        """Return config object for a given path.

        If no config has already been loaded for root (either by calling this function
        or load_configs), this function will search for and load a config file if found.
        """
        if path in self.source_configs:
            return self.source_configs[path]
        config = self._get_config(path)
        self.source_configs[path] = config

        return config

    def _compute_diagnostics(self, document: TextDocument) -> List[lsp.Diagnostic]:
        path = Path(document.path)
        config = self.get_config(path)
        is_excluded = utils.make_exclude_filter(config.exclude)
        if is_excluded(path):
            return []

        return lint(document.source, config, path)

    def compute_diagnostics(self, document: TextDocument):
        # `None` sentinel ensures that `diagnostics` gets updated if the URI is not
        # present.
        _, previous = self.diagnostics.get(document.uri, (0, None))

        diagnostics = self._compute_diagnostics(document)

        # Only update if the list has changed
        if previous != diagnostics:
            self.diagnostics[document.uri] = (document.version, diagnostics)

    def format(
        self,
        document: TextDocument,
        options: lsp.FormattingOptions,
        range: Optional[Tuple[int, int]] = None,
    ):
        path = Path(document.path)
        config = self.get_config(path)

        parser = Parser()

        if config.style_indent is None:
            indent = "\t" if not options.insert_spaces else " " * options.tab_size
        else:
            indent = config.get_indent()

        formatter = Formatter(
            FormatterOpts(
                indent=indent,
                indent_mixed_tab_size=config.get_indent_mixed_tab_size(),
                spaces_in_braces=config.style_spaces_in_braces,
                max_blank_lines=config.style_max_blank_lines,
                indent_namespace_eval=config.style_indent_namespace_eval,
            )
        )

        if range is not None:
            start, end = range
            return formatter.format_partial(document.source[start:end], parser)

        return formatter.format_top(document.source, parser)


server = TclspServer("tclsp", __version__)


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: TclspServer, params: lsp.DidOpenTextDocumentParams):
    """Parse each document when it is opened"""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DID_OPEN, params)
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.compute_diagnostics(doc)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: TclspServer, params: lsp.DidChangeTextDocumentParams):
    """Parse each document when it is changed"""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DID_CHANGE, params)
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.compute_diagnostics(doc)


@server.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(ls: TclspServer, params: lsp.DidCloseTextDocumentParams):
    """Free up resources when a document is closed."""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DID_CLOSE, params)
    doc = ls.workspace.get_text_document(params.text_document.uri)

    try:
        del ls.diagnostics[doc.uri]
    except KeyError:
        pass

    try:
        del ls.source_configs[Path(doc.path)]
    except KeyError:
        pass


@server.feature(
    lsp.TEXT_DOCUMENT_DIAGNOSTIC,
    lsp.DiagnosticOptions(
        identifier="pull-diagnostics",
        inter_file_dependencies=False,
        # We could support workspace diagnostics, although an implementation based on
        # the pygls tutorial seems to add client-server noise for no benefit (it ends up
        # replying to a frequent workspace diagnostics request with "unchanged"
        # messages).
        workspace_diagnostics=False,
    ),
)
def document_diagnostic(ls: TclspServer, params: lsp.DocumentDiagnosticParams):
    """Return diagnostics for the requested document"""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DIAGNOSTIC, params)

    was_cached = True
    if (uri := params.text_document.uri) not in ls.diagnostics:
        was_cached = False
        doc = ls.workspace.get_text_document(uri)
        ls.compute_diagnostics(doc)

    version, diagnostics = ls.diagnostics[uri]
    result_id = f"{uri}@{version}"

    if was_cached and result_id == params.previous_result_id:
        return lsp.UnchangedDocumentDiagnosticReport(result_id)

    return lsp.FullDocumentDiagnosticReport(items=diagnostics, result_id=result_id)


@server.feature(lsp.WORKSPACE_DID_CHANGE_WATCHED_FILES)
def change_watched_files(ls: TclspServer, params: lsp.DidChangeWatchedFilesParams):
    logging.debug("Received %s: %s", lsp.WORKSPACE_DID_CHANGE_WATCHED_FILES, params)

    # Clear diagnostics cache so they get recalculated when requested
    ls.diagnostics = {}

    # Config files changed, clear the many caches!
    ls.config_files = {}
    ls.source_configs = {}
    ls.invalid_configs = set()

    if ls.client_supports_refresh:
        ls.lsp.send_request(lsp.WORKSPACE_DIAGNOSTIC_REFRESH, None)


@server.feature(lsp.TEXT_DOCUMENT_FORMATTING)
def format_document(ls: TclspServer, params: lsp.DocumentFormattingParams):
    """Format the entire document"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    source = doc.source
    start = lsp.Position(line=0, character=0)
    last_line = source.rsplit("\n", 1)[-1]
    end = lsp.Position(line=source.count("\n"), character=len(last_line))

    formatted = ls.format(doc, params.options)
    return [
        lsp.TextEdit(
            range=lsp.Range(start=start, end=end),
            new_text=formatted,
        )
    ]


@server.feature(lsp.TEXT_DOCUMENT_RANGE_FORMATTING)
def format_range(ls: TclspServer, params: lsp.DocumentRangeFormattingParams):
    """Format the given range with a document"""
    doc = ls.workspace.get_text_document(params.text_document.uri)

    # Round up range to full lines.
    start_line = params.range.start.line
    end_line = params.range.end.line
    if params.range.end.character > 0:
        end_line += 1
    range = lsp.Range(
        start=lsp.Position(line=start_line, character=0),
        end=lsp.Position(line=end_line, character=0),
    )

    start = doc.offset_at_position(range.start)
    end = doc.offset_at_position(range.end)

    try:
        formatted = ls.format(doc, params.options, range=(start, end))
    except TclSyntaxError:
        return None

    return [
        lsp.TextEdit(
            range=range,
            new_text=formatted,
        )
    ]


@server.feature(lsp.INITIALIZE)
def initialize(ls: TclspServer, params: lsp.InitializeParams) -> None:
    if params.initialization_options is None:
        return

    # Apply settings provided on initialization. The schema was copied from the template
    # that the tclint-vscode extension is based on.
    globalSettings = params.initialization_options.get("globalSettings", {})
    if globalSettings.get("configPath"):
        path = Path(globalSettings["configPath"]).expanduser()
        if not path.is_absolute():
            ls.show_message(
                f"Warning: expected global config path to be absolute, got {path}"
            )
        else:
            ls.global_settings.config_file = path

    for settings in params.initialization_options.get("settings", []):
        root = Path(settings["cwd"])
        if root not in ls.workspace_settings:
            ls.workspace_settings[root] = ExtensionSettings()
        if settings.get("configPath"):
            path = Path(settings["configPath"]).expanduser()
            if not path.is_absolute():
                path = root / path
            ls.workspace_settings[root].config_file = path


@server.feature(lsp.INITIALIZED)
def init(ls: TclspServer, params: lsp.InitializeParams):
    """Registers file watchers on config filenames so that we can reload configs and
    refresh diagnostics if they've changed.

    Based on code snippet in
    https://github.com/openlawlibrary/pygls/issues/376#issuecomment-1717656614.
    """
    capabilities = ls.client_capabilities.workspace

    try:
        ls.client_supports_refresh = (
            capabilities.diagnostics.refresh_support  # type: ignore[union-attr]
        )
    except AttributeError:
        ls.client_supports_refresh = False

    try:
        client_supports_watched_files_registration = (
            capabilities.did_change_watched_files.dynamic_registration  # type: ignore[union-attr] # noqa: E501
        )
    except AttributeError:
        client_supports_watched_files_registration = False

    if client_supports_watched_files_registration:
        watchers = []
        for filename in (*DEFAULT_CONFIGS, "pyproject.toml"):
            pattern = f"**/{filename}"
            watchers.append(lsp.FileSystemWatcher(glob_pattern=pattern))

        for settings in (ls.global_settings, *ls.workspace_settings.values()):
            if settings.config_file is not None:
                watchers.append(
                    lsp.FileSystemWatcher(glob_pattern=settings.config_file)
                )

        ls.register_capability(
            lsp.RegistrationParams(
                registrations=[
                    lsp.Registration(
                        id=str(uuid.uuid4()),
                        method=lsp.WORKSPACE_DID_CHANGE_WATCHED_FILES,
                        register_options=lsp.DidChangeWatchedFilesRegistrationOptions(
                            watchers=watchers
                        ),
                    )
                ]
            )
        )

    ls.load_workspace_setting_configs()


def main():
    parser = argparse.ArgumentParser("tclsp")
    log_levels = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }
    parser.add_argument(
        "-l",
        "--log-level",
        default="info",
        type=lambda x: x.lower(),
        help="set the log level. defaults to info",
        choices=log_levels.keys(),
    )
    args = parser.parse_args()
    logging.basicConfig(level=log_levels[args.log_level], format="%(message)s")

    server.start_io()


if __name__ == "__main__":
    main()
