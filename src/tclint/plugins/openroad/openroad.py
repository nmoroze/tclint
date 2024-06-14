import subprocess
import re
from typing import Optional, List, Dict

from tclint.plugins.openroad.help_parser import spec_from_help_entry
from tclint.commands.utils import CommandArgError, check_count
from tclint.syntax_tree import BareWord


def check_arg_spec(command, arg_spec):
    # TODO check required arguments
    def check(args, parser):
        args_allowed = set(arg_spec.keys())
        positional_args = []

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
                positional_args.append(arg)
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
                if not arg_spec[contents]["repeated"]:
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

        check = check_count(
            command,
            min=arg_spec[""]["min"],
            max=arg_spec[""]["max"],
            args_name="positional args",
        )
        check(positional_args, parser)

        return None

    return check


_patches = {
    # missing {} around -box metavars
    "detailed_route_debug": {
        "": {"min": 0, "max": 0},
        "-pa": {"required": False, "value": False, "repeated": False},
        "-ta": {"required": False, "value": False, "repeated": False},
        "-dr": {"required": False, "value": False, "repeated": False},
        "-maze": {"required": False, "value": False, "repeated": False},
        "-net": {"required": False, "value": True, "repeated": False},
        "-pin": {"required": False, "value": True, "repeated": False},
        "-box": {"required": False, "value": True, "repeated": False},
        "-dump_last_worker": {"required": False, "value": False, "repeated": False},
        "-iter": {"required": False, "value": True, "repeated": False},
        "-pa_markers": {"required": False, "value": False, "repeated": False},
        "-dump_dr": {"required": False, "value": False, "repeated": False},
        "-dump_dir": {"required": False, "value": True, "repeated": False},
        "-pa_edge": {"required": False, "value": False, "repeated": False},
        "-pa_commit": {"required": False, "value": False, "repeated": False},
        "-write_net_tracks": {"required": False, "value": False, "repeated": False},
    },
    # need to handle pair of switches in exclusive group
    "remove_from_physical_cluster": {
        "": {"min": 1, "max": 1},
        "-parent_module": {"required": False, "value": True, "repeated": False},
        "-modinst": {"required": False, "value": True, "repeated": False},
        "-inst": {"required": False, "value": True, "repeated": False},
        "-physical_cluster": {"required": False, "value": True, "repeated": False},
    },
    # need to handle parens around switches
    "set_bump": {
        "": {"min": 0, "max": 0},
        "-row": {"required": True, "value": True, "repeated": False},
        "-col": {"required": True, "value": True, "repeated": False},
        "-remove": {"required": False, "value": False, "repeated": False},
        "-power": {"required": False, "value": True, "repeated": False},
        "-ground": {"required": False, "value": True, "repeated": False},
        "-net": {"required": False, "value": True, "repeated": False},
    },
    "with_output_to_variable": {
        "": {"min": 1, "max": None},
    },
    # need to fix unclosed [ after -fields
    "report_path": {
        # pin ^|r|rise|v|f|fall
        "": {"min": 2, "max": 2},
        # exclusive
        "-min": {"required": False, "value": False, "repeated": False},
        "-max": {"required": False, "value": False, "repeated": False},
        "-format": {"required": False, "value": True, "repeated": False},
        "-fields": {"required": False, "value": True, "repeated": False},
        "-digits": {"required": False, "value": True, "repeated": False},
        "-no_line_splits": {"required": False, "value": False, "repeated": False},
    },
    # TODO: probably need to evaluate other SDC commands to see if they require
    # repeating values
    "set_clock_groups": {
        "": {"min": 0, "max": 0},
        "-name": {"required": False, "value": True, "repeated": False},
        "-logically_exclusive": {"required": False, "value": False, "repeated": False},
        "-physically_exclusive": {"required": False, "value": False, "repeated": False},
        "-asynchronous": {"required": False, "value": False, "repeated": False},
        "-allow_paths": {"required": False, "value": False, "repeated": False},
        "-comment": {"required": False, "value": True, "repeated": False},
        "-group": {"required": True, "value": True, "repeated": True},
    },
    # Need to fix help string to disambiguate that "-mirror" doesn't consume "name" as a
    # value
    "place_pad": {
        "": {"min": 1, "max": 1},
        "-master": {"required": False, "value": True, "repeated": False},
        "-row": {"required": True, "value": True, "repeated": False},
        "-location": {"required": True, "value": True, "repeated": False},
        "-mirror": {"required": True, "value": False, "repeated": False},
    },
    # help string is missing metavars for most switches that take a value
    "clock_tree_synthesis": {
        "": {"min": 0, "max": 0},
        "-root_buf": {"required": False, "value": True, "repeated": False},
        "-buf_list": {"required": False, "value": True, "repeated": False},
        "-wire_unit": {"required": False, "value": True, "repeated": False},
        "-clk_nets": {"required": False, "value": True, "repeated": False},
        "-sink_clustering_size": {"required": False, "value": True, "repeated": False},
        "-num_static_layers": {"required": False, "value": True, "repeated": False},
        "-sink_clustering_buffer": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-distance_between_buffers": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-branching_point_buffers_distance": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-clustering_exponent": {"required": False, "value": True, "repeated": False},
        "-clustering_unbalance_ratio": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-sink_clustering_max_diameter": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-sink_clustering_levels": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-tree_buf": {"required": False, "value": True, "repeated": False},
        "-sink_clustering_buffer_max_cap_derate": {
            "required": False,
            "value": True,
            "repeated": False,
        },
        "-delay_buffer_derate": {"required": False, "value": True, "repeated": False},
        "-post_cts_disable": {"required": False, "value": False, "repeated": False},
        "-sink_clustering_enable": {
            "required": False,
            "value": False,
            "repeated": False,
        },
        "-balance_levels": {"required": False, "value": False, "repeated": False},
        "-obstruction_aware": {"required": False, "value": False, "repeated": False},
        "-apply_ndr": {"required": False, "value": False, "repeated": False},
        "-dont_use_dummy_load": {"required": False, "value": False, "repeated": False},
    },
    # help string needs to present diode_cell as optional
    "repair_antennas": {
        "": {"min": 0, "max": 1},
        "-iterations": {"required": False, "value": True, "repeated": False},
        "-ratio_margin": {"required": False, "value": True, "repeated": False},
    },
    # Need a way to indicate repeated arguments are okay.
    # TODO: this was unecessary prior to the merge of
    # https://github.com/The-OpenROAD-Project/OpenROAD/pull/5100, if we add a way to
    # apply these to specific versions, that should be enabled here.
    "remove_buffers": {"": {"min": 0, "max": None}},
}


def make_command_spec(exec: Optional[List[str]] = None) -> Dict:
    if exec is not None:
        cmd = exec
    else:
        cmd = ["openroad"]
    cmd += ["-no_init", "-no_splash"]
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
        raise Exception(
            f"openroad exited with non-zero status. stderr: {p.stderr.decode()}"
        )

    help = p.stdout.decode()

    # Preprocessing help output to make it parseable
    # - Strip out comments
    help = re.sub(r"#.*$", "", help, flags=re.MULTILINE)
    # - Remove blank lines
    help = re.sub(r"^\n", "", help, flags=re.MULTILINE)
    # - Collapse each command onto one line
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
