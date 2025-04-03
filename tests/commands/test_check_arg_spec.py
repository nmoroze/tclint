import pytest

from tclint.commands import CommandArgError
from tclint.commands.checks import check_arg_spec
from tclint.syntax_tree import BareWord, ArgExpansion, VarSub


def test_repeated_switch_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": {"min": 0, "max": 0},
        "switches": {
            "-abc": {"required": False, "value": False, "repeated": True},
        },
    }
    assert check_arg_spec("command", spec)(args, None) is None


def test_repeated_switch_not_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": {"min": 0, "max": 0},
        "switches": {
            "-abc": {"required": False, "value": False, "repeated": False},
        },
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_too_many():
    args = [BareWord("foo")]
    spec = {
        "positionals": {"min": 0, "max": 0},
        "switches": {},
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_too_few():
    args = [BareWord("foo")]
    spec = {
        "positionals": {"min": 2, "max": 2},
        "switches": {},
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_unlimited():
    args = [BareWord("foo")] * 10
    spec = {
        "positionals": {"min": 1, "max": None},
        "switches": {},
    }
    check_arg_spec("command", spec)(args, None)


def test_positional_count_arg_expansion():
    args = [BareWord("foo"), ArgExpansion(VarSub("foo"))]
    spec = {
        "positionals": {"min": 3, "max": None},
        "switches": {},
    }
    check_arg_spec("command", spec)(args, None)
