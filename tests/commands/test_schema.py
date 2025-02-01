import pytest
import jsonschema

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

    jsonschema.validate(instance=command_spec, schema=schema)


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

    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=invalid_command_spec, schema=schema)


def test_invalid_minmax_values():
    invalid_minmax_spec = {
        "plugin": "test_plugin",
        "spec": {"command1": {"": {"min": "0", "max": None}}},  # Should be integer
    }

    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=invalid_minmax_spec, schema=schema)


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

    with pytest.raises(jsonschema.exceptions.ValidationError):
        jsonschema.validate(instance=invalid_spec, schema=schema)
