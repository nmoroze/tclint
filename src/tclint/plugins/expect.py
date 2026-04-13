"""Plugin for validating expect commands.

See https://www.tcl-lang.org/man/expect5.31/expect.1.html for reference.
"""

from tclint.commands.builtin import commands as builtins
from tclint.commands.checks import (
    CommandArgError,
    check_arg_spec,
    map_switches,
)


def close(args, parser):
    """close [-slave] [-onexec 0|1] [-i spawn_id]"""

    # Fancy handling since it seems like expect will fall back to Tcl's built-in close
    # if none of its switches match, and we can't express this in a static arg spec.
    # Try to replicate the logic here, reusing the functions used by `check_arg_spec`.

    if len(args) == 0:
        # No args is okay.
        return None

    expect_switches = {
        "-slave": {"required": False, "repeated": False, "value": None},
        "-onexec": {
            "required": False,
            "repeated": False,
            "value": {"type": "any"},
            "metavar": "0|1",
        },
        "-i": {
            "required": False,
            "repeated": False,
            "value": {"type": "any"},
            "metavar": "spawn_id",
        },
    }

    mapped, positionals = map_switches(args, expect_switches, "close", parser)
    if len(mapped) > 0:
        if len(positionals) > 0:
            raise CommandArgError(
                f"too many arguments for close: got {len(positionals)}, expected"
                " no more than 0"
            )
        return None

    return check_arg_spec("close", args, parser, builtins["close"])


commands = {
    "close": close,
    "exit": {
        "positionals": [
            # TODO: break out into switches once we have a way to support -onexit's
            # optional value.
            {"name": "opts", "value": {"type": "variadic"}, "required": False},
            # TODO: add (positive) integer type.
            {"name": "status", "value": {"type": "any"}, "required": False},
        ],
    },
}
