import pytest

from voluptuous import Invalid

from tclint.commands.schema import schema


def test_valid_command_spec():
    command_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "positionals": [
                    {"name": "arg1", "required": True, "value": {"type": "any"}},
                    {"name": "arg2", "required": False, "value": {"type": "variadic"}},
                ],
                "switches": {
                    "-switch1": {
                        "required": False,
                        "value": {"type": "any"},
                        "repeated": False,
                        "metavar": "value1",
                    },
                    "-switch2": {
                        "required": True,
                        "value": None,
                        "repeated": True,
                    },
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
                "switches": {
                    # missing "required"
                    "-switch1": {"value": {"type": "any"}, "repeated": False},
                },
            }
        },
    }

    with pytest.raises(Invalid) as excinfo:
        schema(invalid_command_spec)
    print("test_missing_required_field:", excinfo.value)


def test_invalid_datatype():
    invalid_minmax_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": {
                "switches": {
                    "-switch1": {
                        "required": True,
                        "value": {"type": "any"},
                        "repeated": "invalid",  # Should be a boolean
                    }
                },
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
                "positionals": [
                    {
                        "name": "arg1",
                        "required": True,
                        "value": {"type": "any"},
                        "extra_field": "not allowed",  # Extra property not in schema
                    }
                ],
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
                        "positionals": [
                            {
                                "name": "arg1",
                                "required": True,
                                "value": {"type": "any"},
                            },
                        ],
                    },
                    "subcommand2": None,
                    "": {
                        "switches": {
                            "-switch1": {
                                "required": False,
                                "value": {"type": "any"},
                                "repeated": False,
                            },
                        },
                    },
                }
            }
        },
    }
    schema(command_spec)


def test_applies_defaults():
    command_spec = {
        "name": "test_plugin",
        "commands": {"command1": {}, "command2": {"subcommands": {"subcommand1": {}}}},
    }
    validated = schema(command_spec)
    for key in ("positionals", "switches"):
        assert key in validated["commands"]["command1"]
        assert key in validated["commands"]["command2"]["subcommands"]["subcommand1"]


def test_functions():
    """For Python plugins, command specs can be functions."""
    command_spec = {
        "name": "test_plugin",
        "commands": {
            "command1": lambda args, parser: None,
            "command2": {"subcommands": {"subcommand1": lambda args, parser: None}},
        },
    }
    schema(command_spec)
