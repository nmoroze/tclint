"""Main CLI entry point."""

import argparse
import codecs
import os
import pathlib
import sys
from typing import List

from tclint.config import get_config, ConfigError, Config
from tclint.parser import Parser, TclSyntaxError
from tclint.checks import IndentLevelChecker, SpacingChecker, LineChecker, Violation

try:
    from tclint._version import __version__
except ModuleNotFoundError:
    __version__ = "(unknown version)"

# exit code flags
EXIT_OK = 0
EXIT_LINT_VIOLATIONS = 1
EXIT_SYNTAX_ERROR = 2
EXIT_INPUT_ERROR = 4


def resolve_sources(
    paths: List[pathlib.Path], exclude: List[pathlib.Path] = None
) -> List[pathlib.Path]:
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
            # if relative_to returns successfully, that means the current path
            # is under an excluded path, and should be ignored
            # TODO: if we drop Python 3.8 support, we can use is_relative_to()
            try:
                resolved_path.relative_to(exclude_path)
                return True
            except ValueError:
                pass

        return False

    sources = []

    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"path {path} does not exist")

        if is_excluded(path):
            continue

        if path.is_file():
            sources.append(path)
            continue

        assert path.is_dir()

        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                _, ext = os.path.splitext(name)
                if ext in EXTENSIONS:
                    child = pathlib.Path(dirpath) / name
                    if not is_excluded(child):
                        sources.append(child)

    return sources


def lint(script: str, config: Config, debug=False) -> List[Violation]:
    parser = Parser(debug=debug)

    violations = []
    tree = parser.parse(script)
    violations += parser.violations

    if debug:
        print(tree.pretty())

    for checker in (IndentLevelChecker(), SpacingChecker(), LineChecker()):
        violations += checker.check(script, tree, config)

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
    parser.add_argument("source", nargs="+", help="files to lint", type=pathlib.Path)
    parser.add_argument("--debug", action="store_true", help="display debug output")
    parser.add_argument(
        "-c", "--config", help="path to config file", type=pathlib.Path, default=None
    )
    args = parser.parse_args()

    try:
        config = get_config(args.config)
    except ConfigError as e:
        print(f"Invalid config file: {e}")
        return EXIT_INPUT_ERROR

    try:
        sources = resolve_sources(args.source, exclude=config.exclude)
    except FileNotFoundError as e:
        print(f"Invalid path provided: {e}")
        return EXIT_INPUT_ERROR

    retcode = EXIT_OK

    for path in sources:
        with open(path, "r", errors="replace_with_warning") as f:
            script = f.read()

        try:
            violations = lint(script, config, debug=args.debug)
        except TclSyntaxError as e:
            print(f"{path}: syntax error: {e}")
            retcode |= EXIT_SYNTAX_ERROR
            continue

        violations = [v for v in violations if v.id not in config.ignore]

        for violation in sorted(violations):
            print(f"{path}:{violation}")

        if len(violations) > 0:
            retcode |= EXIT_LINT_VIOLATIONS

    return retcode


if __name__ == "__main__":
    sys.exit(main())
