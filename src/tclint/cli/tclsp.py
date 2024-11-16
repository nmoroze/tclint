import argparse
import logging
from pathlib import Path
from typing import List
import uuid

from lsprotocol import types as lsp

from pygls.server import LanguageServer
from pygls.workspace import TextDocument
from pygls.uris import to_fs_path

from tclint import tclint
from tclint.config import get_config, DEFAULT_CONFIGS, Config, ConfigError
from tclint.format import Formatter, FormatterOpts
from tclint.lexer import TclSyntaxError
from tclint.parser import Parser

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"


DIAGNOSTIC_SOURCE = "tclint"


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


class TclspServer(LanguageServer):
    """Main server class. Implements pull diagnostics using a method adapted from
    https://pygls.readthedocs.io/en/latest/examples/pull-diagnostics.html."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diagnostics = {}
        # maps root path -> RunConfig, since there may be more than one workspace.
        self.configs = {}
        self.client_supports_refresh = False

    def get_roots(self) -> List[Path]:
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

    def load_configs(self):
        self.configs = {}
        for root in self.get_roots():
            config = None
            try:
                config = get_config(None, root)
            except ConfigError as e:
                self.show_message(f"Error loading config file: {e}")

            if config is not None:
                for other in self.configs.keys():
                    if root.is_relative_to(other) or other.is_relative_to(root):
                        self.show_message(
                            f"Warning: found configs in overlapping workspaces: {root},"
                            f" {other}. It's undefined which will apply."
                        )

                self.configs[root] = config

    def get_config(self, path: Path) -> Config:
        matching_config = Config()
        for root, config in self.configs.items():
            if path.is_relative_to(root):
                matching_config = config.get_for_path(path)
                break
        return matching_config

    def parse(self, document: TextDocument):
        path = Path(document.path)
        config = self.get_config(path)

        # `None` sentinel ensures that `diagnostics` gets updated if the URI is not
        # present.
        _, previous = self.diagnostics.get(document.uri, (0, None))
        diagnostics = lint(document.source, config, path)

        # Only update if the list has changed
        if previous != diagnostics:
            self.diagnostics[document.uri] = (document.version, diagnostics)

    def format(self, document: TextDocument, options: lsp.FormattingOptions):
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
                spaces_in_braces=config.style_spaces_in_braces,
                max_blank_lines=config.style_max_blank_lines,
                indent_namespace_eval=config.style_indent_namespace_eval,
            )
        )
        return formatter.format_top(document.source, parser)


server = TclspServer("tclsp", __version__)


@server.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: TclspServer, params: lsp.DidOpenTextDocumentParams):
    """Parse each document when it is opened"""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DID_OPEN, params)
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.parse(doc)


@server.feature(lsp.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: TclspServer, params: lsp.DidOpenTextDocumentParams):
    """Parse each document when it is changed"""
    logging.debug("Received %s: %s", lsp.TEXT_DOCUMENT_DID_CHANGE, params)
    doc = ls.workspace.get_text_document(params.text_document.uri)
    ls.parse(doc)


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
        ls.parse(doc)

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

    ls.load_configs()
    if ls.client_supports_refresh:
        ls.lsp.send_request(lsp.WORKSPACE_DIAGNOSTIC_REFRESH, None)


@server.feature(lsp.TEXT_DOCUMENT_FORMATTING)
def format_document(ls: TclspServer, params: lsp.DocumentFormattingParams):
    """Format the entire document"""
    doc = ls.workspace.get_text_document(params.text_document.uri)
    formatted = ls.format(doc, params.options)
    return [
        lsp.TextEdit(
            range=lsp.Range(
                start=lsp.Position(line=0, character=0),
                end=lsp.Position(line=len(formatted.split("\n")) + 1, character=0),
            ),
            new_text=formatted,
        )
    ]


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

    ls.load_configs()


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
