from collections.abc import Callable

from voluptuous import Optional, Or, Schema, Self

_switch_value = Or({"type": "any"}, {"type": "int"}, None)
_positional_value = Or(
    {"type": "any"},
    {"type": "int"},
    {"type": "variadic"},
    {"type": "script"},
    {"type": "expression"},
)

# Need to define this as a Schema with required=True to ensure that this requirement
# persists through the Or in the main schema definition.
_command_args = Schema(
    {
        Optional("positionals", default=[]): [
            {
                "name": str,
                "required": bool,
                "value": _positional_value,
            }
        ],
        Optional("switches", default={}): {
            Optional(str): {
                "required": bool,
                "repeated": bool,
                "value": _switch_value,
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
