import pytest

from voluptuous import Invalid

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

    schema(command_spec)


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

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_command_spec)
    print("test_missing_required_field:", excinfo.value)


def test_invalid_minmax_values():
    invalid_minmax_spec = {
        "plugin": "test_plugin",
        "spec": {"command1": {"": {"min": "0", "max": None}}},  # Should be integer
    }

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_minmax_spec)
    print("test_invalid_minmax_values:", excinfo.value)


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

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_spec)
    print("test_extra_property:", excinfo.value)
