import pytest

from tclint.commands import CommandArgError
from tclint.plugins.openroad.openroad import check_arg_spec
from tclint.syntax_tree import BareWord


def test_repeated_switch_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "": {"min": 0, "max": 0},
        "-abc": {"required": False, "value": False, "repeated": True},
    }
    assert check_arg_spec("command", spec)(args, None) is None


def test_repeated_switch_not_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "": {"min": 0, "max": 0},
        "-abc": {"required": False, "value": False, "repeated": False},
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)
