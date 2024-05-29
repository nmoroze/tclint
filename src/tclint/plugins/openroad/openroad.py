import os
import subprocess
import re

from tclint.plugins.openroad.help_parser import spec_from_help_entry
from tclint.commands.utils import CommandArgError
from tclint.syntax_tree import ArgExpansion, BareWord


def check_arg_spec(command, arg_spec):
    def check(args, parser):
        args_allowed = set(arg_spec.keys())
        positional_args_allowed = arg_spec[""]["max"]

        has_argsub = any([isinstance(a, ArgExpansion) for a in args])

        args = list(args)
        while len(args) > 0:
            arg = args.pop(0)

            # To facilitate better error messages, we expect that switches are always
            # specified as BareWords that start with "-" or ">". This lets us throw an
            # error when a switch-like thing doesn't match any supported arguments,
            # rather than counting it towards the positional arguments (which usually
            # ends up in a vague "too many arguments" error). To make tclint interpret a
            # switch-like word as a positional argument, users should wrap it in "", and
            # any switches should be BareWords.
            contents = arg.contents
            if not (
                isinstance(arg, BareWord) and contents and contents[0] in {"-", ">"}
            ):
                positional_args_allowed -= 1
                continue

            if contents in args_allowed:
                if arg_spec[contents]["value"]:
                    try:
                        args.pop(0)
                    except IndexError:
                        raise CommandArgError(
                            f"invalid arguments for {command}: expected value after"
                            f" {contents}"
                        )
                args_allowed.remove(contents)
            elif contents in arg_spec:
                raise CommandArgError(f"duplicate argument for {command}: {contents}")
            else:
                prefix_matches = []
                for switch in arg_spec:
                    if switch.startswith(contents):
                        prefix_matches.append(switch)

                if len(prefix_matches) == 1:
                    raise CommandArgError(
                        f"shortened argument for {command}: expand {contents} to"
                        f" {prefix_matches[0]}"
                    )

                if len(prefix_matches) > 1:
                    raise CommandArgError(
                        f"ambiguous argument for {command}: {contents} could be any of"
                        f" {', '.join(prefix_matches)}"
                    )

                raise CommandArgError(
                    f"unrecognized argument for {command}: {contents}"
                )

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
    "with_output_to_variable": {
        # TODO: technically infinite? currently not supported though
        "": {"min": 1, "max": 2},
    },
    # need to fix unclosed [ after -fields
    "report_path": {
        # pin ^|r|rise|v|f|fall
        "": {"min": 2, "max": 2},
        # exclusive
        "-min": {"required": False, "value": False},
        "-max": {"required": False, "value": False},
        "-format": {"required": False, "value": True},
        "-fields": {"required": False, "value": True},
        "-digits": {"required": False, "value": True},
        "-no_line_splits": {"required": False, "value": False},
    },
}


def make_command_spec():
    cmd = []
    if "TCLINT_OR_CONTAINER" in os.environ:
        # TODO: bit of a hack for my own debugging... need to determine how to work
        # this into UX
        cmd += ["docker", "run", "-i", os.environ["TCLINT_OR_CONTAINER"]]
    cmd += ["openroad", "-no_init", "-no_splash"]
    input = "help; exit"

    try:
        p = subprocess.run(
            cmd,
            input=input.encode(),
            capture_output=True,
        )
    except FileNotFoundError:
        raise Exception("openroad not installed")

    if p.returncode != 0:
        print("Warning: openroad exited with non-zero status")
        print(f" stderr: {p.stderr}")

    help = p.stdout.decode()

    # collapsing each command on one line makes parsing easier
    help = re.sub(r"\n +", " ", help)

    command_spec = {}

    for line in help.split("\n"):
        if not line or line.startswith("openroad>"):
            # skip empty line or prompt line
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
        command: check_arg_spec(command, arg_spec)
        for command, arg_spec in command_spec.items()
    }
