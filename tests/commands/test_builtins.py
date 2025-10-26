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
        ("foreach", False),
        (r"foreach $iters {}", False),
        (r"foreach {*}$iters {}", True),
    ],
)
def test_validation(command, valid):
    parser = Parser()
    parser.parse(command)

    assert len(parser.violations) == 0 if valid else 1


def test_foreach_arg_expansion_only():
    parser = Parser()
    parser.parse("foreach {*}$args")

    assert len(parser.violations) == 1
    assert not str(parser.violations[0]).startswith("1:1: insufficient args")
    assert str(parser.violations[0]).startswith("1:1: expected braced word")


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


def test_if_valid():
    parser = Parser()

    for script in [
        "if 1 {}",
        "if 1 {} {}",
        "if 1 {} elseif 1 {}",
        "if 1 {} elseif 1 {} {}",
        "if 1 then {}",
        "if 1 {} else {}",
        "if 1 {} elseif 1 then {}",
        "if 1 {} elseif 1 {} else {}",
    ]:
        parser.parse(script)
        assert len(parser.violations) == 0


def test_if_invalid():
    parser = Parser()

    n = 0
    for script in [
        "if 1",
        "if 1 {} else",
        "if 1 {} else {} {}",
        "if 1 {} elseif",
        "if 1 {} elseif 1",
        "if 1 {} elseif 1 {} else",
        "if 1 {} elseif 1 {} else {} {}",
    ]:
        n += 1
        parser.parse(script)
        assert len(parser.violations) == n
