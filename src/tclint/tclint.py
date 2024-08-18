"""Main CLI entry point."""

import argparse
import pathlib
import sys
from typing import List, Optional


from tclint.config import get_config, setup_config_cli_args, Config, ConfigError
from tclint.parser import Parser, TclSyntaxError
from tclint.checks import get_checkers
from tclint.violations import Violation, Rule
from tclint.comments import CommentVisitor
from tclint.cli.utils import resolve_sources, register_codec_warning
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
    script: str,
    config: Config,
    path: Optional[pathlib.Path],
    no_check_style=False,
    debug=0,
) -> List[Violation]:
    plugins = [config.commands] if config.commands is not None else []
    parser = Parser(debug=(debug > 0), command_plugins=plugins)

    violations = []
    tree = parser.parse(script)
    violations += parser.violations

    if debug > 0:
        print(tree.pretty(positions=(debug > 1)))

    for checker in get_checkers(no_check_style):
        violations += checker.check(script, tree, config)

    v = CommentVisitor()
    ignore_lines = v.run(tree, path)
    violations = filter_violations(violations, config.ignore, ignore_lines, path)

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
    parser.add_argument(
        "--show-categories",
        help="print category tag for each violation",
        action="store_true",
    )
    parser.add_argument(
        "--no-check-style",
        help="skip style checks (besides line length)",
        action="store_true",
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
                no_check_style=args.no_check_style,
                debug=args.debug,
            )
        except TclSyntaxError as e:
            line, col = e.pos
            print(f"{out_prefix}:{line}:{col}: syntax error: {e}")
            retcode |= EXIT_SYNTAX_ERROR
            continue

        for violation in sorted(violations):
            print(f"{out_prefix}:{violation.str(show_category=args.show_categories)}")

        if len(violations) > 0:
            retcode |= EXIT_LINT_VIOLATIONS

    return retcode


if __name__ == "__main__":
    sys.exit(main())
