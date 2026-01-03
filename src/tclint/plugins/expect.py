"""Plugin for validating expect commands.

See https://www.tcl-lang.org/man/expect5.31/expect.1.html for reference.
"""

commands = {
    "close": {
        "switches": {
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
    },
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
