from schema import Schema, Optional, Or

_command_schema = Schema({
    "": {
        "min": int,
        "max": Or(int, None),
    },
    Optional(str): {
        "required": bool,
        "value": bool,
        "repeated": bool,
    },
})

schema = Schema({
    "plugin": str,
    "spec": {
        Optional(str): _command_schema,
    },
})
