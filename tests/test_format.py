import pathlib

from tclint.syntax_tree import (
    Script,
    Command,
    BareWord,
)

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
  } elseif { expr $i % 5 == 0 } {
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


def test_one_cmd_per_line():
    """Formatter breaks up commands on same line."""
    TREE = Script(
        Command(BareWord("foo"), pos=(1, 1), end_pos=(1, 4)),
        Command(BareWord("foo"), pos=(1, 5), end_pos=(1, 8)),
    )
    expected = "foo\nfoo"

    assert Formatter().format_top(TREE) == expected
