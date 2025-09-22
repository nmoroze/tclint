from tclint.commands.checks import arg_count
from tclint.parser import Parser
from tclint import syntax_tree as ast


def test_arg_count():
    parser = Parser()
    assert arg_count([ast.BareWord("foo"), ast.BareWord("bar")], parser) == (2, False)
    assert arg_count([ast.ArgExpansion(ast.BracedWord("foo bar"))], parser) == (
        2,
        False,
    )
    # Returns minimum possible number of arguments.
    assert arg_count([ast.ArgExpansion(ast.VarSub("foo"))], parser) == (0, True)
