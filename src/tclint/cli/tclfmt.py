"""CLI utility for formatting Tcl code."""

# TODO: Add modes
# - --in-place (modifies files in-place)
# - --check (status code, doesn't modify files)
# - Optional: --dif

import argparse
import pathlib
import sys

from tclint.cli.utils import resolve_sources, register_codec_warning
from tclint.config import get_config, setup_config_cli_args, Config, ConfigError
from tclint.parser import Parser, TclSyntaxError
from tclint.format import Formatter

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"

# exit code flags
EXIT_OK = 0
EXIT_FORMAT_VIOLATIONS = 1
EXIT_SYNTAX_ERROR = 2
EXIT_INPUT_ERROR = 4


def format(script: str, config: Config, debug=0) -> str:
    plugins = [config.commands] if config.commands is not None else []
    parser = Parser(debug=(debug > 0), command_plugins=plugins)

    tree = parser.parse(script)

    if debug > 0:
        print(tree.pretty(positions=(debug > 1)))

    formatter = Formatter()
    return formatter.format_top(tree)


def main():
    parser = argparse.ArgumentParser("tclfmt")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "source",
        nargs="+",
        help="files to format. Provide '-' to read from stdin",
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
        # TODO: we should eventually allow tclfmt to find a config by walking up
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
            formatted = format(script, config.get_for_path(path), debug=args.debug)
            print(formatted)
        except TclSyntaxError as e:
            line, col = e.pos
            print(f"{out_prefix}:{line}:{col}: syntax error: {e}", file=sys.stderr)
            retcode |= EXIT_SYNTAX_ERROR
            continue

    return retcode


if __name__ == "__main__":
    sys.exit(main())
