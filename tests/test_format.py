import pathlib

from tclint.format import Formatter
from tclint.parser import Parser
from tclint.config import Config

MY_DIR = pathlib.Path(__file__).parent.resolve()


def _test(script, expected):
    parser = Parser()
    tree = parser.parse(script)
    format = Formatter(Config(style_indent=2))
    out = format.format_top(tree)

    assert out == expected + "\n"


def test_fizzbuzz():
    with open(MY_DIR / "data" / "dirty.tcl", "r") as f:
        script = f.read()

    expected = r"""
for { set i 1 } { $i < 100 } { incr i } {
  if { $i % 15 == 0 } {
    puts "FizzBuzz"
  } elseif { $i % 3 == 0 } {
    puts "Fizz"
  } elseif { [expr $i % 5] == 0 } {
    puts "Buzz"
  } else {
    puts $i
  }
}""".strip()

    _test(script, expected)


def test_blank_lines():
    """Formatter preserves up to two blank lines."""
    script = r"""
foo

foo


foo



foo"""

    expected = r"""
foo

foo


foo


foo""".strip()

    _test(script, expected)


def test_multiple_cmds_per_line():
    """Formatter preserves commands on same line."""
    script = "foo; foo"
    _test(script, script)


def test_comments():
    """Formatter preserves comments and normalizes spacing (indent, spaces between
    command and inline comment)."""
    script = r"""
# this is foo
foo;     # foo"""

    expected = r"""
# this is foo
foo ;# foo""".strip()

    _test(script, expected)


def test_switch():
    script = r"""
switch $arg {
        a {
        foo } b {
      bar
    }}
"""

    expected = r"""
switch $arg {
  a {
    foo
  } b {
    bar
  }
}""".strip()

    _test(script, expected)


def test_no_reindent_braced_word():
    """We can't add an extra level of indent in the second line of the braced word,
    since this will change the actual text."""
    script = r"""
puts \
{ one
  two }
"""

    expected = r"""
puts \
  { one
  two }""".strip()

    _test(script, expected)


def test_no_reindent_braced_word_script():
    """We can't add an extra level of indent in the second line of the braced word,
    since this will change the actual text."""
    script = r"""
if { 1 } {
puts { one
  two }
}"""

    expected = r"""
if { 1 } {
  puts { one
  two }
}""".strip()

    _test(script, expected)


def test_reindent_command_sub():
    script = r"""
puts [command \
foo]"""

    expected = r"""
puts [command \
        foo]
""".strip()

    _test(script, expected)


def test_reindent_command_sub_new_line():
    script = r"""
puts \
[command \
foo]"""

    expected = r"""
puts \
  [command \
     foo]
""".strip()

    _test(script, expected)


def test_expr_align():
    script = r"""
if {$a && $b &&
$c } { puts "asdf" }"""

    expected = r"""
if { $a && $b &&
     $c } { puts "asdf" }""".strip()

    _test(script, expected)


def test_ternary_op_align():
    script = r"""
expr { $foo ? 2
    + 3 :
    4 }"""

    expected = r"""
expr { $foo ? 2
       + 3 :
       4 }""".strip()

    _test(script, expected)


def test_expr_command_sub_alignment():
    script = r"""
if { ![command $arg1 \
    $arg2 \
    $arg3] } {
    return true
}"""

    expected = r"""
if { ![command $arg1 \
         $arg2 \
         $arg3] } {
  return true
}""".strip()

    _test(script, expected)


def test_indent_bare_word_command_sub():
    script = r"""
puts foo[bar\
    "mootown"]qwerty"""

    expected = r"""
puts foo[bar \
           "mootown"]qwerty
""".strip()

    _test(script, expected)


def test_varsub_index_preserve_newline():
    script = r"""i
puts $foo(asdf \
asdf)""".strip()

    _test(script, script)


def test_varsub_indent_format():
    script = r"""
$foo(asdf$asdf[asdf \
-asdf] [qwerty \
-uiop])"""

    expected = r"""
$foo(asdf$asdf[asdf \
                 -asdf] [qwerty \
                           -uiop])""".strip()

    _test(script, expected)


def test_braced_varsub():
    script = r"${one_two}_three"
    _test(script, script)


def test_function():
    script = r"expr { max($a, $b) }"
    _test(script, script)


def test_dont_add_trailing_space_indent():
    script = r"""
if { 1 } {
puts "one"

puts "two"
}"""

    expected = r"""
if { 1 } {
  puts "one"

  puts "two"
}""".strip()

    _test(script, expected)


def test_paren_format():
    script = r"""
expr { 1 + (2 *
       3) }"""

    expected = r"""
expr { 1 + (2 *
            3) }""".strip()

    _test(script, expected)


def test_expr_alignment_nested():
    """Original indentation implementations failed when we had a doubly nested binop
    before other sub-expression types."""
    script = r"""
expr { 1 + 2 && !($foo ||
$bar) }"""

    expected = r"""
expr { 1 + 2 && !($foo ||
                  $bar) }""".strip()

    _test(script, expected)

    script = r"""
expr { 1 + 2 + min($a,
    $b,
    $c) }"""

    expected = r"""
expr { 1 + 2 + min($a,
                   $b,
                   $c) }""".strip()

    _test(script, expected)

    script = r"""
expr { 1 + 2 * [command \
    -foo\
    -bar] }
"""

    expected = r"""
expr { 1 + 2 * [command \
                  -foo \
                  -bar] }""".strip()
    _test(script, expected)

    script = r"""
expr { $foo
* 5 + (2 * (3 * 4) + 5 + 7
* 16 + (2
* 3)) }"""

    expected = r"""
expr { $foo
       * 5 + (2 * (3 * 4) + 5 + 7
              * 16 + (2
                      * 3)) }""".strip()

    _test(script, expected)
