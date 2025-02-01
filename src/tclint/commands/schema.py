"""JSON Schema defining command specs."""

_command_schema = {
    "type": "object",
    "properties": {
        "": {
            "type": "object",
            "properties": {
                "min": {
                    "type": "integer",
                    "description": "Minimum number of arguments",
                },
                "max": {
                    "type": ["integer", "null"],
                    "description": "Maximum number of arguments. Null means unlimited.",
                },
            },
            "additionalProperties": False,
            "required": ["min", "max"],
        }
    },
    "patternProperties": {
        "^.+": {
            "type": "object",
            "properties": {
                "required": {
                    "type": "boolean",
                    "description": "Whether this switch is required",
                },
                "value": {
                    "type": "boolean",
                    "description": "Whether this switch takes a value",
                },
                "repeated": {
                    "type": "boolean",
                    "description": "Whether this switch can be repeated",
                },
            },
            "additionalProperties": False,
            "required": ["required", "value", "repeated"],
        }
    },
}

schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Command Spec",
    "description": "Describes a set of commands and their arguments.",
    "type": "object",
    "properties": {
        "plugin": {
            "type": "string",
            "description": "The name of the plugin associated with this command spec.",
        },
        "spec": {"type": "object", "patternProperties": {"^.+": _command_schema}},
    },
    "additionalProperties": False,
}
