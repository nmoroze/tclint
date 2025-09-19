import pytest

from tclint.parser import Parser
from tclint.syntax_tree import Script, Command, BareWord, QuotedWord


@pytest.mark.parametrize(
    "command,valid",
    [
        ("namespace path", True),
        (r"namespace path {path1 path2}", True),
        ("namespace path path1 path2", False),
        ("namespace upvar", False),
        ("namespace upvar my_namespace", True),
        ("namespace upvar my_namespace var0 var1 var2", True),
        ("namespace unknown", True),
        ("namespace unknown puts hello", False),
        ("break", True),
        ("break asdf", False),
    ],
)
def test_validation(command, valid):
    parser = Parser()
    parser.parse(command)

    assert len(parser.violations) == 0 if valid else 1


def test_namespace_unknown_script():
    script = r"""namespace unknown {
        puts "hello"
    }"""
    parser = Parser()
    tree = parser.parse(script)
    assert tree == Script(
        Command(
            BareWord("namespace"),
            BareWord("unknown"),
            Script(Command(BareWord("puts"), QuotedWord(BareWord("hello")))),
        )
    )
