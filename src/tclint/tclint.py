"""Main CLI entry point."""

import argparse
import codecs
import os
import pathlib
import sys
from typing import List, Optional

from tclint.config import get_config, setup_config_cli_args, Config, ConfigError
from tclint.parser import Parser, TclSyntaxError
from tclint.checks import get_checkers
from tclint.violations import Violation, Rule
from tclint.comments import CommentVisitor
from tclint import utils

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"

# exit code flags
EXIT_OK = 0
EXIT_LINT_VIOLATIONS = 1
EXIT_SYNTAX_ERROR = 2
EXIT_INPUT_ERROR = 4


def resolve_sources(
    paths: List[pathlib.Path], exclude: Optional[List[pathlib.Path]] = None
) -> List[Optional[pathlib.Path]]:
    """Resolves paths passed via CLI to a list of filepaths to lint.

    `paths` is a list of paths that may be files or directories. Files are
    returned verbatim if they exist, and directories are recursively searched
    for files that have the extension .tcl, .xdc, or .sdc. Paths that match or
    are underneath a path provided in `exclude` are ignored.

    Raises FileNotFoundError if a supplied path does not exist.
    """
    # Extensions that may indicate tcl files
    # TODO: make configurable
    EXTENSIONS = [".tcl", ".xdc", ".sdc"]

    if exclude is None:
        exclude = []
    exclude = [path.resolve() for path in exclude]

    def is_excluded(path):
        resolved_path = path.resolve()
        for exclude_path in exclude:
            # if the current path is under an excluded path it should be ignored
            if utils.is_relative_to(resolved_path, exclude_path):
                return True

        return False

    sources: List[Optional[pathlib.Path]] = []

    for path in paths:
        if str(path) == "-":
            sources.append(None)
            continue

        if not path.exists():
            raise FileNotFoundError(f"path {path} does not exist")

        if is_excluded(path):
            continue

        if not path.is_dir():
            sources.append(path)
            continue

        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                _, ext = os.path.splitext(name)
                if ext in EXTENSIONS:
                    child = pathlib.Path(dirpath) / name
                    if not is_excluded(child):
                        sources.append(child)

    return sources


def filter_violations(
    violations, config_ignore, inline_ignore, path: Optional[pathlib.Path]
):
    global_ignore = []
    if path is not None:
        path = path.resolve()
    for entry in config_ignore:
        if isinstance(entry, Rule):
            global_ignore.append(entry)
        elif path is not None:
            ignore_path = entry["path"].resolve()
            if utils.is_relative_to(path, ignore_path):
                global_ignore.extend(entry["rules"])

    filtered_violations = []

    for violation in violations:
        if violation.id in global_ignore:
            continue
        line = violation.pos[0]
        if line in inline_ignore and violation.id in inline_ignore[line]:
            continue

        filtered_violations.append(violation)

    return filtered_violations


def lint(
    script: str, config: Config, path: Optional[pathlib.Path], debug=0
) -> List[Violation]:
    parser = Parser(debug=(debug > 0), command_plugins=config.command_plugins)

    violations = []
    tree = parser.parse(script)
    violations += parser.violations

    if debug > 0:
        print(tree.pretty(positions=(debug > 1)))

    for checker in get_checkers():
        violations += checker.check(script, tree, config)

    v = CommentVisitor()
    ignore_lines = v.run(tree, path)
    violations = filter_violations(violations, config.ignore, ignore_lines, path)

    return violations


def replace_with_warning_handler(e):
    # TODO: formal warning mechanism, include path
    print("Warning: non-unicode characters in file, replacing with �")
    return codecs.replace_errors(e)


codecs.register_error("replace_with_warning", replace_with_warning_handler)


def main():
    parser = argparse.ArgumentParser("tclint")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "source",
        nargs="+",
        help="files to lint. Provide '-' to read from stdin",
        type=pathlib.Path,
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        default=0,
        help=(
            "display debug output. Provide additional times to increase the verbosity"
            " of output (e.g. -dd)"
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        help="path to config file",
        type=pathlib.Path,
        default=None,
        metavar="<path>",
    )
    setup_config_cli_args(parser)
    args = parser.parse_args()

    try:
        config = get_config(args.config)
    except ConfigError as e:
        print(f"Invalid config file: {e}")
        return EXIT_INPUT_ERROR

    config.apply_cli_args(args)

    try:
        sources = resolve_sources(args.source, exclude=config.exclude)
    except FileNotFoundError as e:
        print(f"Invalid path provided: {e}")
        return EXIT_INPUT_ERROR

    retcode = EXIT_OK

    for path in sources:
        if path is None:
            script = sys.stdin.read()
            out_prefix = "(stdin)"
        else:
            with open(path, "r", errors="replace_with_warning") as f:
                script = f.read()
            out_prefix = str(path)

        try:
            violations = lint(script, config.get_for_path(path), path, debug=args.debug)
        except TclSyntaxError as e:
            line, col = e.pos
            print(f"{out_prefix}:{line}:{col}: syntax error: {e}")
            retcode |= EXIT_SYNTAX_ERROR
            continue

        for violation in sorted(violations):
            print(f"{out_prefix}:{violation}")

        if len(violations) > 0:
            retcode |= EXIT_LINT_VIOLATIONS

    return retcode


if __name__ == "__main__":
    sys.exit(main())
