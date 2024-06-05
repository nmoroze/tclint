import argparse
import json
import shlex
import sys

from tclint.commands.plugins import PluginManager

try:
    from tclint._version import __version__  # type: ignore
except ModuleNotFoundError:
    __version__ = "(unknown version)"


def make_cmd_spec(args) -> int:
    plugin_name = args.plugin
    plugin = PluginManager.get_mod(plugin_name)
    if plugin is None:
        print(f"Unable to make command spec for {plugin_name}")
        return 1

    if not hasattr(plugin, "make_command_spec"):
        print(f"Plugin {plugin_name} does not support command spec generation")
        return 1

    exec_cmd = None
    if args.exec is not None:
        exec_cmd = shlex.split(args.exec)

    make_command_spec = getattr(plugin, "make_command_spec")
    try:
        command_spec = make_command_spec(exec_cmd)
    except Exception as e:
        print(f"Error encountered while generating command spec: {e}")
        return 1

    output_path = f"{args.plugin}.json" if args.output is None else args.output
    with open(output_path, "w") as out_file:
        json.dump({"plugin": plugin_name, "spec": command_spec}, out_file)
        print(f"Wrote command spec to {output_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        "tclint-plugins", description="tclint plugin manager"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    subparsers = parser.add_subparsers(required=True)

    cmd_spec_parser = subparsers.add_parser(
        "make-spec", help="generate command spec from installed tool"
    )
    cmd_spec_parser.set_defaults(func=make_cmd_spec)
    cmd_spec_parser.add_argument("plugin", help="name of plugin to generate spec for")
    cmd_spec_parser.add_argument(
        "-o", "--output", metavar="<path>", help="path to store command spec"
    )
    cmd_spec_parser.add_argument(
        "-e",
        "--exec",
        metavar="<cmd>",
        help="path to binary or shell invocation for tool",
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
