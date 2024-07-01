import pathlib

from tclint.syntax_tree import Script, Command, Comment, BareWord, VarSub, List

from tclint.format import Formatter
from tclint.parser import Parser

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_fizzbuzz():
    with open(MY_DIR / "data" / "dirty.tcl", "r") as f:
        script = f.read()

    parser = Parser()
    tree = parser.parse(script)

    EXPECTED = """for { set i 1 } { $i < 100 } { incr i } {
  if { $i % 15 == 0 } {
    puts "FizzBuzz"
  } elseif { $i % 3 == 0 } {
    puts "Fizz"
  } elseif { [expr $i % 5] == 0 } {
    puts "Buzz"
  } else {
    puts $i
  }
}"""

    format = Formatter()
    out = format.format_top(tree)

    assert out == EXPECTED


def test_blank_lines():
    """Formatter preserves up to two blank lines."""
    TREE = Script(
        Command(BareWord("foo"), pos=(1, 1), end_pos=(1, 4)),
        Command(BareWord("foo"), pos=(3, 1), end_pos=(3, 4)),
        Command(BareWord("foo"), pos=(6, 1), end_pos=(6, 4)),
        Command(BareWord("foo"), pos=(10, 1), end_pos=(10, 4)),
    )

    expected = "foo\n\nfoo\n\n\nfoo\n\n\nfoo"

    assert Formatter().format_top(TREE) == expected


def test_multiple_cmds_per_line():
    """Formatter preserves commands on same line."""
    TREE = Script(
        Command(BareWord("foo"), pos=(1, 1), end_pos=(1, 4)),
        Command(BareWord("foo"), pos=(1, 5), end_pos=(1, 8)),
    )
    expected = "foo; foo"

    assert Formatter().format_top(TREE) == expected


def test_comments():
    """Formatter preserves comments and normalizes spacing (indent, spaces between
    command and inline comment)."""
    TREE = Script(
        Comment(" this is foo", pos=(1, 3), end_pos=(1, 16)),
        Command(
            BareWord("foo", pos=(2, 1), end_pos=(2, 4)), pos=(2, 1), end_pos=(2, 4)
        ),
        Comment(" foo", pos=(2, 8), end_pos=(2, 13)),
        pos=(1, 1),
        end_pos=(3, 1),
    )

    expected = """# this is foo
foo  ;# foo"""

    assert Formatter().format_top(TREE) == expected


def test_switch():
    TREE = Script(
        Command(
            BareWord("switch", pos=(1, 1), end_pos=(1, 7)),
            VarSub("arg", pos=(1, 8), end_pos=(1, 12)),
            List(
                BareWord("a", pos=(2, 9), end_pos=(2, 10)),
                Script(
                    Command(
                        BareWord("foo", pos=(3, 9), end_pos=(3, 12)),
                        pos=(3, 9),
                        end_pos=(3, 12),
                    ),
                    pos=(2, 11),
                    end_pos=(4, 6),
                ),
                BareWord("b", pos=(5, 1), end_pos=(5, 2)),
                Script(
                    Command(
                        BareWord("bar", pos=(6, 5), end_pos=(6, 8)),
                        pos=(6, 5),
                        end_pos=(6, 8),
                    ),
                    pos=(5, 3),
                    end_pos=(7, 6),
                ),
                pos=(1, 13),
                end_pos=(8, 6),
            ),
            pos=(1, 1),
            end_pos=(8, 6),
        ),
        pos=(1, 1),
        end_pos=(10, 1),
    )

    expected = """switch $arg {
  a {
    foo
  } b {
    bar
  }
}"""

    assert Formatter().format_top(TREE) == expected
