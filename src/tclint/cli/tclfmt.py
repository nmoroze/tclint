"""CLI utility for formatting Tcl code."""

import argparse
import pathlib
import sys

from tclint.cli.utils import resolve_sources, register_codec_warning
from tclint.config import get_config, setup_tclfmt_config_cli_args, Config, ConfigError
from tclint.parser import Parser, TclSyntaxError
from tclint.format import Formatter, FormatterOpts

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"

# exit code flags
EXIT_OK = 0
EXIT_FORMAT_VIOLATIONS = 1
EXIT_SYNTAX_ERROR = 2
EXIT_INPUT_ERROR = 4


def format(script: str, config: Config, debug=False) -> str:
    plugins = [config.commands] if config.commands is not None else []
    parser = Parser(debug=debug, command_plugins=plugins)

    if config.style_indent == "tab":
        indent = "\t"
    elif isinstance(config.style_indent, int):
        indent = " " * config.style_indent
    else:
        raise ValueError(
            f"unexpected value for config.style_indent: {config.style_indent}"
        )

    formatter = Formatter(
        FormatterOpts(
            indent=indent,
            spaces_in_braces=config.style_spaces_in_braces,
            max_blank_lines=config.style_max_blank_lines,
            indent_namespace_eval=config.style_indent_namespace_eval,
        )
    )
    return formatter.format_top(script, parser)


def check(path: pathlib.Path, script: str, formatted: str):
    parser = Parser()
    original_tree = parser.parse(script)
    formatted_tree = parser.parse(formatted)
    if original_tree != formatted_tree:
        print(f"Warning: {path} syntax trees don't match", file=sys.stderr)
        print("\n".join(original_tree.diff(formatted_tree)), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser("tclfmt")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    parser.add_argument(
        "source",
        nargs="+",
        help=(
            "files to format. By default, prints formatted files to stdout. Provide '-'"
            " to read from stdin"
        ),
        type=pathlib.Path,
    )

    mode_group = parser.add_argument_group("mode")
    mode_mutex = mode_group.add_mutually_exclusive_group(required=False)
    mode_mutex.add_argument(
        "--in-place", help="update files that require formatting", action="store_true"
    )
    mode_mutex.add_argument(
        "--check",
        help="list files that require formatting and set the exit code",
        action="store_true",
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
    setup_tclfmt_config_cli_args(parser)
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

    reformat_count = 0
    for path in sources:
        if path is None:
            script = sys.stdin.read()
            out_prefix = "(stdin)"
        else:
            with open(path, "r", errors="replace_with_warning") as f:
                script = f.read()
            out_prefix = str(path)

        try:
            formatted = format(
                script, config.get_for_path(path), debug=(args.debug > 1)
            )
            if args.in_place and path:
                with open(path, "w") as f:
                    f.write(formatted)
            elif args.check:
                if script != formatted:
                    print(f"{out_prefix}: needs reformatting")
                    retcode |= EXIT_FORMAT_VIOLATIONS
                    reformat_count += 1
            else:
                if args.in_place:
                    print("Warning: --in-place option ignored when reading from stdin")
                print(formatted, end="")

            if args.debug > 0:
                check(path, script, formatted)
        except TclSyntaxError as e:
            line, col = e.pos
            print(f"{out_prefix}:{line}:{col}: syntax error: {e}", file=sys.stderr)
            retcode |= EXIT_SYNTAX_ERROR
            continue

    if args.check:
        messages = []
        if reformat_count == 0:
            messages.append("Formatting clean!")
        elif reformat_count == 1:
            messages.append("1 file needs reformatting.")
        else:
            messages.append(f"{reformat_count} files need reformatting.")
        messages.append(
            f"Checked {len(sources)} file{'s' if len(sources) != 1 else ''}."
        )
        print(" ".join(messages))

    return retcode


if __name__ == "__main__":
    sys.exit(main())
