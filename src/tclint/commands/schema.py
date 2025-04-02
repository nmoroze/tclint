from voluptuous import Schema, Optional, Or

# Need to define this as a Schema with required=True to ensure that this requirement
# persists through the Or in the main schema definition.
_command_schema = Schema(
    {
        "": {
            "min": int,
            "max": Or(int, None),
        },
        Optional(str): {
            "required": bool,
            "value": bool,
            "repeated": bool,
        },
    },
    required=True,
)

schema = Schema(
    {
        "plugin": str,
        "spec": {Optional(str): Or(_command_schema, None)},
    },
    required=True,
)
