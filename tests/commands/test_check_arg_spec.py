import contextlib
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


@pytest.mark.parametrize(
    "args,valid",
    [
        ([BareWord("foo"), BareWord("arg1")], True),
        ([BareWord("foo")], False),  # missing required argument
        ([BareWord("bar"), BareWord("-asdf")], True),
        ([BareWord("baz"), BareWord("quz")], True),
        ([BareWord("baz")], False),  # missing subcommand
        ([BareWord("-default"), BareWord("val")], True),
        ([BareWord("arg1")], False),
    ],
)
def test_subcommands(args, valid):
    spec = {
        "subcommands": {
            "foo": {
                "positionals": {"min": 1, "max": 1},
                "switches": {},
            },
            "bar": None,
            "baz": {
                "subcommands": {
                    "quz": None,
                }
            },
            "": {
                "positionals": {"min": 0, "max": 0},
                "switches": {
                    "-default": {"required": True, "value": True, "repeated": False}
                },
            },
        }
    }
    check = check_arg_spec("command", spec)

    if valid:
        cm = contextlib.nullcontext(None)
    else:
        cm = pytest.raises(CommandArgError)
    with cm as excinfo:
        check(args, None)

    if excinfo is not None:
        print(excinfo.value)
