import pytest

from tclint import syntax_tree as ast
from tclint.commands import CommandArgError
from tclint.commands.checks import arg_count, map_positionals
from tclint.parser import Parser


def test_arg_count():
    parser = Parser()
    assert arg_count([ast.BareWord("foo"), ast.BareWord("bar")], parser) == (2, False)
    assert arg_count([ast.ArgExpansion(ast.BracedWord("foo bar"))], parser) == (
        2,
        False,
    )
    # Returns minimum possible number of arguments.
    assert arg_count([ast.ArgExpansion(ast.VarSub("foo"))], parser) == (0, True)


def test_map_positionals():
    # From puts
    spec = [
        {"name": "-nonewline", "value": {"type": "any"}, "required": False},
        {"name": "channelId", "value": {"type": "any"}, "required": False},
        {"name": "string", "value": {"type": "any"}, "required": True},
    ]

    # `puts -nonewline $channel "Hello"``
    args = [ast.BareWord("-nonewline"), ast.VarSub("channel"), ast.QuotedWord("Hello")]
    mapping = map_positionals(args, spec, "puts")
    assert mapping == [[0], [1], [2]]

    # `puts $channel "Hello"``
    args = [ast.VarSub("channel"), ast.QuotedWord("Hello")]
    mapping = map_positionals(args, spec, "puts")
    assert mapping == [[0], [2]]
    # TODO: We'd expect the following. However, I don't think we can get here until an
    # "options" type is implemented in the positionals spec.
    # assert mapping == [(1,), (2,)]

    # `puts -nonewline "Hello"``
    args = [ast.BareWord("-nonewline"), ast.QuotedWord("Hello")]
    mapping = map_positionals(args, spec, "puts")
    assert mapping == [[0], [2]]

    # `puts "Hello"``
    args = [ast.QuotedWord("Hello")]
    mapping = map_positionals(args, spec, "puts")
    assert mapping == [[2]]

    # `puts this has too many args`
    args = [
        ast.BareWord("this"),
        ast.BareWord("has"),
        ast.BareWord("too"),
        ast.BareWord('many"'),
        ast.BareWord("arguments"),
    ]
    expected = "too many arguments for puts: got 5, expected no more than 3"
    with pytest.raises(CommandArgError, match=expected):
        map_positionals(args, spec, "puts")

    foreach_spec = [
        {"name": "varList", "value": {"type": "any"}, "required": True},
        {"name": "list", "value": {"type": "any"}, "required": True},
        {"name": "varList list", "value": {"type": "variadic"}, "required": False},
        {"name": "command", "value": {"type": "any"}, "required": True},
    ]

    # # `foreach {*}$iters { cmd }`
    args = [ast.ArgExpansion(ast.VarSub("iters")), ast.BracedWord("cmd")]
    mapping = map_positionals(args, foreach_spec, "foreach")
    assert mapping == [[0, 1], [3]]

    # `foreach i {0 1} j {0 1} k {0 1} { cmd }`
    args = [
        ast.BareWord("i"),
        ast.BracedWord("0 1"),
        ast.BareWord("j"),
        ast.BracedWord("0 1"),
        ast.BareWord("k"),
        ast.BracedWord("0 1"),
        ast.BracedWord("cmd"),
    ]
    mapping = map_positionals(args, foreach_spec, "foreach")
    assert mapping == [[0], [1], [2], [2], [2], [2], [3]]

    # `foreach i { cmd }`
    args = [ast.BareWord("i"), ast.BracedWord("cmd")]
    expected = "missing required argument for foreach: command"
    with pytest.raises(CommandArgError, match=expected):
        map_positionals(args, foreach_spec, "foreach")

    # Is there a real example of this among built-in Tcl?
    # TODO: if so, ensure we test against what we'd expect.
    spec = [
        {"name": "foo", "value": {"type": "any"}, "required": False},
        {"name": "bar", "value": {"type": "any"}, "required": False},
        {"name": "baz", "value": {"type": "any"}, "required": True},
    ]
    args = [ast.BareWord("a"), ast.BareWord("b")]
    mapping = map_positionals(args, spec, "foo")
    assert mapping == [[0], [2]]

    spec = [
        {"name": "foo", "value": {"type": "any"}, "required": True},
        {"name": "bar", "value": {"type": "any"}, "required": False},
        {"name": "baz", "value": {"type": "any"}, "required": False},
    ]
    args = [ast.BareWord("a"), ast.BareWord("b")]
    mapping = map_positionals(args, spec, "foo")
    assert mapping == [[0], [1]]

    # An arg expansion of zero args may be legal, but we should probably flag since
    # there's no reason to do it. Ideally, capture this as a specific violation.
    spec = [{"name": "foo", "value": {"type": "any"}, "required": True}]
    args = [ast.ArgExpansion(ast.VarSub("args")), ast.BareWord("foo")]
    expected = "too many arguments for foo: got 2, expected no more than 1"
    with pytest.raises(CommandArgError, match=expected):
        map_positionals(args, spec, "foo")

    catch_spec = [
        {"name": "script", "value": {"type": "any"}, "required": True},
        {"name": "resultVarName", "value": {"type": "any"}, "required": False},
        {"name": "optionsVarName", "value": {"type": "any"}, "required": False},
    ]
    # `catch { cmd } {*}$catchopts`
    args = [ast.BracedWord("cmd"), ast.ArgExpansion(ast.VarSub("catchopts"))]
    mapping = map_positionals(args, catch_spec, "foo")
    assert mapping == [[0], [1]]

    # Check message for missing two arguments.
    spec = [
        {"name": "foo", "value": {"type": "any"}, "required": True},
        {"name": "bar", "value": {"type": "any"}, "required": True},
    ]
    args = []
    expected = "missing required arguments for foo: foo, bar"
    with pytest.raises(CommandArgError, match=expected):
        map_positionals(args, spec, "foo")
