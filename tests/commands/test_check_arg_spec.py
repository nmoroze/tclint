import contextlib
import pytest

from tclint.commands import CommandArgError
from tclint.commands.checks import check_arg_spec
from tclint.syntax_tree import BareWord, ArgExpansion, VarSub, BracedWord


def test_repeated_switch_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": [],
        "switches": {
            "-abc": {"required": False, "value": None, "repeated": True},
        },
    }
    check_arg_spec("command", args, None, spec)


def test_repeated_switch_not_allowed():
    args = [BareWord("-abc"), BareWord("-abc")]
    spec = {
        "positionals": [],
        "switches": {
            "-abc": {"required": False, "value": None, "repeated": False},
        },
    }
    with pytest.raises(CommandArgError):
        check_arg_spec("command", args, None, spec)


def test_positional_count_too_many():
    args = [BareWord("foo")]
    spec = {"positionals": [], "switches": {}}
    with pytest.raises(CommandArgError):
        check_arg_spec("command", args, None, spec)


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
        check_arg_spec("command", args, None, spec)


def test_positional_count_unlimited():
    args = [BareWord("foo")] * 10
    spec = {
        "positionals": [
            {"name": "args", "value": {"type": "variadic"}, "required": True}
        ],
        "switches": {},
    }
    check_arg_spec("command", args, None, spec)


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
    check_arg_spec("command", args, None, spec)


def test_required_switch():
    spec = {
        "positionals": [],
        "switches": {
            "-foo": {
                "required": True,
                "value": None,
                "repeated": False,
            },
            "-bar": {
                "required": False,
                "value": None,
                "repeated": False,
            },
        },
    }

    check_arg_spec("command", [BareWord("-foo"), BareWord("-bar")], None, spec)
    check_arg_spec("command", [BareWord("-foo")], None, spec)

    with pytest.raises(CommandArgError) as excinfo:
        check_arg_spec("command", [BareWord("-bar")], None, spec)
    if excinfo is not None:
        print(excinfo.value)

    with pytest.raises(CommandArgError) as excinfo:
        check_arg_spec("command", [], None, spec)
    if excinfo is not None:
        print(excinfo.value)


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

    if valid:
        cm = contextlib.nullcontext(None)
    else:
        cm = pytest.raises(CommandArgError)
    with cm as excinfo:
        check_arg_spec("command", args, None, spec)

    if excinfo is not None:
        print(excinfo.value)


def test_arg_replacement_subcommands():
    args = [BareWord("subcommand"), BracedWord("arg")]

    def _parse(args, _):
        return [BareWord(args[0].contents)]

    spec = {
        "subcommands": {
            "subcommand": _parse,
        }
    }
    new_args = check_arg_spec("command", args, None, spec)
    assert new_args == [BareWord("subcommand"), BareWord("arg")]


def test_no_switches():
    # Tcl command: append l -1
    args = [BareWord("l"), BareWord("-1")]
    spec = {
        "positionals": [
            {"name": "varname", "value": {"type": "any"}, "required": True},
            {"name": "value", "value": {"type": "variadic"}, "required": False},
        ],
        "switches": {},
    }
    check_arg_spec("command", args, None, spec)

    # Tcl command: puts -nonewline stdout foo
    args = [BareWord("-nonewline"), BareWord("stdout"), BareWord("foo")]
    spec = {
        "positionals": [
            {"name": "-nonewline", "value": {"type": "any"}, "required": False},
            {"name": "channelId", "value": {"type": "any"}, "required": False},
            {"name": "string", "value": {"type": "any"}, "required": True},
        ],
        "switches": {},
    }
    check_arg_spec("command", args, None, spec)
