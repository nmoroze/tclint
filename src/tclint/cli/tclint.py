"""Main CLI entry point."""

import argparse
import pathlib
import sys
from typing import Dict, List, Optional


from tclint.config import (
    get_config,
    setup_config_cli_args,
    Config,
    ConfigError,
    RunConfig,
)
from tclint.parser import Parser, TclSyntaxError
from tclint.checks import get_checkers
from tclint.violations import Violation, Rule
from tclint.comments import CommentVisitor
from tclint.cli.utils import resolve_sources, register_codec_warning

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"

# exit code flags
EXIT_OK = 0
EXIT_LINT_VIOLATIONS = 1
EXIT_SYNTAX_ERROR = 2
EXIT_INPUT_ERROR = 4


def filter_violations(
    violations: List[Violation],
    config_ignore: List[Rule],
    inline_ignore: Dict[int, List[Rule]],
) -> List[Violation]:
    filtered_violations = []

    for violation in violations:
        if violation.id in config_ignore:
            continue
        line = violation.start[0]
        if line in inline_ignore and violation.id in inline_ignore[line]:
            continue

        filtered_violations.append(violation)

    return filtered_violations


def lint(
    script: str,
    config: Config,
    path: Optional[pathlib.Path],
    debug=0,
) -> List[Violation]:
    plugins = [config.commands] if config.commands is not None else []
    parser = Parser(debug=(debug > 0), command_plugins=plugins)

    violations = []
    tree = parser.parse(script)
    violations += parser.violations

    if debug > 0:
        print(tree.pretty(positions=(debug > 1)))

    for checker in get_checkers():
        violations += checker.check(script, tree, config)

    v = CommentVisitor()
    ignore_lines = v.run(tree, path)
    violations = filter_violations(violations, config.ignore, ignore_lines)

    return violations


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
        config = get_config(args.config, pathlib.Path())
    except ConfigError as e:
        print(f"Invalid config file: {e}")
        return EXIT_INPUT_ERROR

    if config is None:
        config = RunConfig()

    config.apply_cli_args(args)

    try:
        # TODO: we should eventually allow tclint to find a config by walking up
        # directories, at which point exclude_root should be the parent dir of
        # the config file, unless -c is used (eslint rules)
        exclude_root = pathlib.Path.cwd()
        sources = resolve_sources(
            args.source,
            exclude_patterns=config.exclude,
            exclude_root=exclude_root,
            extensions=config.extensions,
        )
    except FileNotFoundError as e:
        print(f"Invalid path provided: {e}")
        return EXIT_INPUT_ERROR

    retcode = EXIT_OK

    register_codec_warning("replace_with_warning")

    for path in sources:
        if path is None:
            script = sys.stdin.read()
            out_prefix = "(stdin)"
        else:
            with open(path, "r", errors="replace_with_warning") as f:
                script = f.read()
            out_prefix = str(path)

        try:
            violations = lint(
                script,
                config.get_for_path(path),
                path,
                debug=args.debug,
            )
        except TclSyntaxError as e:
            line, col = e.start
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
