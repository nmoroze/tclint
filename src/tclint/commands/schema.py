from voluptuous import Schema, Optional, Or

# Need to define this as a Schema with required=True to ensure that this requirement
# persists through the Or in the main schema definition.
_command_args = Schema(
    {
        "positionals": {
            "min": int,
            "max": Or(int, None),
        },
        "switches": {
            Optional(str): {
                "required": bool,
                "value": bool,
                "repeated": bool,
            }
        },
    },
    required=True,
)

_command_schema = Schema({Optional(str): Or(_command_args, None)}, required=True)

schema = Schema(
    {"name": str, "commands": _command_schema},
    required=True,
)
