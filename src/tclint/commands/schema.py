from collections.abc import Callable

from voluptuous import Optional, Or, Schema, Self

SCALAR_VALUE_TYPES = ("any", "string", "bool", "int", "float", "list")
POSITIONAL_VALUE_TYPES = SCALAR_VALUE_TYPES + ("variadic", "script", "expression")
SWITCH_VALUE_TYPES = SCALAR_VALUE_TYPES


_switch_value = Or(*({"type": value_type} for value_type in SWITCH_VALUE_TYPES), None)
_positional_value = Or(*({"type": value_type} for value_type in POSITIONAL_VALUE_TYPES))

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


def format_validation_error(spec: object, error: Exception) -> str:
    error_path = list(getattr(error, "path", []))
    if error_path and error_path[-1] == "type":
        invalid_value = _get_spec_value(spec, error_path)
        if "switches" in error_path:
            expected = ", ".join(SWITCH_VALUE_TYPES)
        elif "positionals" in error_path:
            expected = ", ".join(POSITIONAL_VALUE_TYPES)
        else:
            expected = None

        if expected is not None:
            return (
                f"invalid value {invalid_value!r} for {_format_error_path(error_path)};"
                f" expected one of {expected}"
            )

    return str(error)


def _get_spec_value(spec: object, path: list[object]) -> object:
    value = spec
    for part in path:
        if isinstance(value, list) and isinstance(part, int):
            value = value[part]
            continue

        if not isinstance(value, dict):
            return None

        value = value.get(part)

    return value


def _format_error_path(path: list[object]) -> str:
    formatted = "data"
    for part in path:
        formatted += f"[{part!r}]"
    return formatted
