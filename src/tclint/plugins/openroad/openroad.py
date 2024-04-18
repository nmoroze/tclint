import subprocess
import re
import tempfile

from tclint.plugins.openroad.help_parser import spec_from_help_entry
from tclint.commands.utils import CommandArgError
from tclint.syntax_tree import ArgExpansion


def _check_arg_spec(command, arg_spec):
    def check(args, parser):
        args_allowed = set(arg_spec.keys())
        positional_args_allowed = arg_spec[""]["max"]

        has_argsub = any([isinstance(a, ArgExpansion) for a in args])

        args = list(args)
        while len(args) > 0:
            arg = args.pop(0)
            contents = arg.contents
            if contents is None:
                positional_args_allowed -= 1
                continue

            if contents in args_allowed:
                if arg_spec[contents]["value"]:
                    try:
                        args.pop(0)
                    except IndexError:
                        raise CommandArgError(f"expected value after {contents}")
                args_allowed.remove(contents)
            else:
                if contents in arg_spec:
                    raise CommandArgError(f"duplicate argument {contents}")
                positional_args_allowed -= 1

        if not has_argsub and positional_args_allowed < 0:
            raise CommandArgError(f"too many arguments for {command}")

        return None

    return check


_patches = {
    # missing {} around -box metavars
    "detailed_route_debug": {
        "": {"min": 0, "max": 0},
        "-pa": {"required": False, "value": False},
        "-ta": {"required": False, "value": False},
        "-dr": {"required": False, "value": False},
        "-maze": {"required": False, "value": False},
        "-net": {"required": False, "value": True},
        "-pin": {"required": False, "value": True},
        "-box": {"required": False, "value": True},
        "-dump_last_worker": {"required": False, "value": False},
        "-iter": {"required": False, "value": True},
        "-pa_markers": {"required": False, "value": False},
        "-dump_dr": {"required": False, "value": False},
        "-dump_dir": {"required": False, "value": True},
        "-pa_edge": {"required": False, "value": False},
        "-pa_commit": {"required": False, "value": False},
        "-write_net_tracks": {"required": False, "value": False},
    },
    # need to handle pair of switches in exclusive group
    "remove_from_physical_cluster": {
        "": {"min": 1, "max": 1},
        "-parent_module": {"required": False, "value": True},
        "-modinst": {"required": False, "value": True},
        "-inst": {"required": False, "value": True},
        "-physical_cluster": {"required": False, "value": True},
    },
    # need to handle parens around switches
    "set_bump": {
        "": {"min": 0, "max": 0},
        "-row": {"required": True, "value": True},
        "-col": {"required": True, "value": True},
        "-remove": {"required": False, "value": False},
        "-power": {"required": False, "value": True},
        "-ground": {"required": False, "value": True},
        "-net": {"required": False, "value": True},
    },
}


def make_command_spec():
    with tempfile.NamedTemporaryFile() as out_file:
        input = f"help > {out_file.name}; exit"
        try:
            subprocess.run(
                ["openroad", "-no_init"],
                input=input.encode(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
        except FileNotFoundError:
            raise Exception("openroad not installed")
        except subprocess.CalledProcessError:
            print("Warning: openroad exited with non-zero status")

        help = out_file.read()

    # collapsing each command on one line makes parsing easier
    help = re.sub(r"\n\s+", " ", help.decode())

    command_spec = {}

    for line in help.split("\n"):
        if not line:
            # skip empty line
            continue

        command_name = line.split()[0]
        if command_name in _patches:
            command_spec[command_name] = _patches[command_name]
        else:
            try:
                command_spec.update(spec_from_help_entry(line))
            except Exception:
                print(
                    f"Warning: failed to parse help string for {command_name}, this"
                    " command will not be documented"
                )

    return command_spec


def commands_from_spec(command_spec):
    return {
        command: _check_arg_spec(command, arg_spec)
        for command, arg_spec in command_spec.items()
    }
