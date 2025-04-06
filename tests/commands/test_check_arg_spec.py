import contextlib
import pytest

from tclint.commands import CommandArgError
from tclint.commands.checks import check_arg_spec
from tclint.syntax_tree import BareWord, ArgExpansion, VarSub


def test_repeated_switch_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": [],
        "switches": {
            "-abc": {"required": False, "value": None, "repeated": True},
        },
    }
    assert check_arg_spec("command", spec)(args, None) is None


def test_repeated_switch_not_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": [],
        "switches": {
            "-abc": {"required": False, "value": None, "repeated": False},
        },
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_too_many():
    args = [BareWord("foo")]
    spec = {"positionals": [], "switches": {}}
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_too_few():
    args = [BareWord("foo")]
    spec = {
        "positionals": [
            {"name": "arg1", "value": {"type": "any"}, "required": True},
            {"name": "arg2", "value": {"type": "any"}, "required": True},
        ],
        "switches": {},
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", spec)(args, None)


def test_positional_count_unlimited():
    args = [BareWord("foo")] * 10
    spec = {
        "positionals": [
            {"name": "args", "value": {"type": "variadic"}, "required": True}
        ],
        "switches": {},
    }
    check_arg_spec("command", spec)(args, None)


def test_positional_count_arg_expansion():
    args = [BareWord("foo"), ArgExpansion(VarSub("foo"))]
    spec = {
        "positionals": [
            {"name": "arg1", "value": {"type": "any"}, "required": True},
            {"name": "arg2", "value": {"type": "any"}, "required": True},
            {"name": "remaining", "value": {"type": "variadic"}, "required": True},
        ],
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
                "positionals": [
                    {"name": "arg1", "required": True, "value": {"type": "any"}}
                ],
                "switches": {},
            },
            "bar": None,
            "baz": {
                "subcommands": {
                    "quz": None,
                }
            },
            "": {
                "positionals": [],
                "switches": {
                    "-default": {
                        "required": True,
                        "value": {"type": "any"},
                        "repeated": False,
                    }
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
