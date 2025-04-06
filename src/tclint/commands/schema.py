from collections.abc import Callable
from voluptuous import Schema, Optional, Or, Self

# Need to define this as a Schema with required=True to ensure that this requirement
# persists through the Or in the main schema definition.
_command_args = Schema(
    {
        Optional("positionals", default=[]): [
            {
                "name": str,
                "required": bool,
                "value": Or({"type": "any"}, {"type": "variadic"}),
            }
        ],
        Optional("switches", default={}): {
            Optional(str): {
                "required": bool,
                "repeated": bool,
                "value": Or({"type": "any"}, None),
                Optional("metavar"): str,
            }
        },
    },
    required=True,
)

commands_schema = Schema(
    {Optional(str): Or(_command_args, None, {"subcommands": Self}, Callable)},
    required=True,
)

schema = Schema(
    {"name": str, "commands": commands_schema},
    required=True,
)
