import pytest

from voluptuous import Invalid

from tclint.commands.schema import schema


def test_valid_command_spec():
    command_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "positionals": {"min": 0, "max": None},
                "switches": {
                    "-switch1": {"required": False, "value": True, "repeated": False},
                    "-switch2": {"required": True, "value": False, "repeated": True},
                },
            }
        },
    }

    schema(command_spec)


def test_missing_required_field():
    invalid_command_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "positionals": {"min": 0, "max": None},
                "switches": {
                    "-switch3": {"value": True, "repeated": False},
                },
            }
        },
    }

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_command_spec)
    print("test_missing_required_field:", excinfo.value)


def test_invalid_minmax_values():
    invalid_minmax_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "positionals": {"min": "0", "max": None},  # Should be integer
                "switches": {},
            }
        },
    }

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_minmax_spec)
    print("test_invalid_minmax_values:", excinfo.value)


def test_extra_property():
    invalid_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "positionals": {
                    "min": 0,
                    "max": None,
                    "extra_field": "not allowed",  # Extra property not in schema
                },
                "switches": {},
            }
        },
    }

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_spec)
    print("test_extra_property:", excinfo.value)


def test_command_no_validation():
    command_spec = {
        "name": "test_plugin",
        "commands": {
            "command": None,
        },
    }

    schema(command_spec)


def test_subcommands():
    command_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "subcommands": {
                    "subcommand1": {
                        "positionals": {"min": 1, "max": 2},
                        "switches": {},
                    },
                    "subcommand2": None,
                    "": {
                        "positionals": {"min": 0, "max": None},
                        "switches": {},
                    },
                }
            }
        },
    }
    schema(command_spec)
