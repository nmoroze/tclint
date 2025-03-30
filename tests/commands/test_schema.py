import pytest

from schema import SchemaError

from tclint.commands.schema import schema


def test_valid_command_spec():
    command_spec = {
        "plugin": "test_plugin",
        "spec": {
            "command1": {
                "": {"min": 0, "max": None},
                "-switch1": {"required": False, "value": True, "repeated": False},
                "-switch2": {"required": True, "value": False, "repeated": True},
            }
        },
    }

    schema.validate(command_spec)


def test_missing_required_field():
    invalid_command_spec = {
        "plugin": "test_plugin",
        "spec": {
            "command1": {
                "": {"min": 0, "max": None},
                "-switch3": {"value": True, "repeated": False},
            }
        },
    }

    with pytest.raises(SchemaError) as excinfo:
        schema.validate(invalid_command_spec)
    print(excinfo.value)


def test_invalid_minmax_values():
    invalid_minmax_spec = {
        "plugin": "test_plugin",
        "spec": {"command1": {"": {"min": "0", "max": None}}},  # Should be integer
    }

    with pytest.raises(SchemaError) as excinfo:
        schema.validate(invalid_minmax_spec)
    print(excinfo.value)


def test_extra_property():
    invalid_spec = {
        "plugin": "test_plugin",
        "spec": {
            "command1": {
                "": {
                    "min": 0,
                    "max": None,
                    "extra_field": "not allowed",  # Extra property not in schema
                }
            }
        },
    }

    with pytest.raises(SchemaError) as excinfo:
        schema.validate(invalid_spec)
    print(excinfo.value)
