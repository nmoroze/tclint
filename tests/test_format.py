import pathlib

from tclint.format import Formatter, FormatterOpts
from tclint.parser import Parser

MY_DIR = pathlib.Path(__file__).parent.resolve()


def _test(
    script,
    expected,
    indent="  ",
    spaces_in_braces=True,
    max_blank_lines=2,
    indent_namespace_eval=True,
):
    parser = Parser()
    format = Formatter(
        FormatterOpts(
            indent=indent,
            spaces_in_braces=spaces_in_braces,
            max_blank_lines=max_blank_lines,
            indent_namespace_eval=indent_namespace_eval,
        )
    )
    out = format.format_top(script, parser)

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

    expected = r"""
foo

foo

foo

foo""".strip()
    _test(script, expected, max_blank_lines=1)


def test_multiple_cmds_per_line():
    """Formatter preserves commands on same line."""
    script = "foo; foo"
    _test(script, script)


def test_comments():
    """Formatter preserves comments, but will update indentation and enforce a single
    space between command and inline comment."""
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
if {
  $a && $b &&
  $c
} { puts "asdf" }""".strip()

    _test(script, expected)


def test_ternary_op_align():
    script = r"""
expr { $foo ? 2
    + 3 :
    4 }"""

    expected = r"""
expr {
  $foo ? 2
  + 3 :
  4
}""".strip()

    _test(script, expected)


def test_expr_command_sub_alignment():
    script = r"""
if { ![command $arg1 \
    $arg2 \
    $arg3] } {
    return true
}"""

    expected = r"""
if {
  ![command $arg1 \
    $arg2 \
    $arg3]
} {
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
    script = r"""
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
expr {
  1 + (2 *
    3)
}""".strip()

    _test(script, expected)


def test_expr_alignment_nested():
    """Original indentation implementations failed when we had a doubly nested binop
    before other sub-expression types."""
    script = r"""
expr { 1 + 2 && !($foo ||
$bar) }"""

    expected = r"""
expr {
  1 + 2 && !($foo ||
    $bar)
}""".strip()

    _test(script, expected)

    script = r"""
expr { 1 + 2 + min($a,
    $b,
    $c) }"""

    expected = r"""
expr {
  1 + 2 + min($a,
    $b,
    $c)
}""".strip()

    _test(script, expected)

    script = r"""
expr { 1 + 2 * [command \
    -foo\
    -bar] }
"""

    expected = r"""
expr {
  1 + 2 * [command \
    -foo \
    -bar]
}""".strip()
    _test(script, expected)

    script = r"""
expr { $foo
* 5 + (2 * (3 * 4) + 5 + 7
* 16 + (2
* 3)) }"""

    expected = r"""
expr {
  $foo
  * 5 + (2 * (3 * 4) + 5 + 7
    * 16 + (2
      * 3))
}""".strip()

    _test(script, expected)


def test_indent_namespace_eval():
    script = r"""
namespace eval my_namespace {
    foo
}"""

    expected_no_indent = r"""
namespace eval my_namespace {
foo
}""".strip()

    expected_indent = r"""
namespace eval my_namespace {
  foo
}""".strip()

    _test(script, expected_no_indent, indent_namespace_eval=False)
    _test(script, expected_indent, indent_namespace_eval=True)


def test_indent_script_in_expr():
    script = r"""
expr {1 + 5 + [if {1} {
return 1
} else {
return 2
}]}"""

    # TODO: is this the format we want?
    expected = r"""
expr {
  1 + 5 + [if { 1 } {
    return 1
  } else {
    return 2
  }]
}""".strip()

    _test(script, expected)


def test_remove_lines_at_ends_of_script():
    script = r"""

proc foo {} {

    puts "asdf"

}

"""

    expected = r"""
proc foo {} {
  puts "asdf"
}""".strip()

    _test(script, expected)


def test_disable():
    script = r"""
command1
 command2 ; # tclfmt-disable
  command3
 command4; # tclfmt-enable
 command5"""

    expected = r"""
command1
command2 ;# tclfmt-disable
  command3
 command4; # tclfmt-enable
command5""".strip()

    _test(script, expected)


def test_quoted_expr():
    script = r"""
if "1 + 2 > 0" {
  puts "foo"
}""".strip()

    _test(script, script)


def test_multiple_commands_in_command_sub():
    script = r"""
[command; command]
""".strip()
    _test(script, script)

    script = r"""
puts [
  command1
  command2
]""".strip()
    _test(script, script)


def test_preserve_comment_line():
    script = r"""
if { 1 } { # tclint-disable-line
}""".strip()
    _test(script, script)


def test_add_indent_expr():
    script = r"""
expr {
1
}
"""

    expected = r"""
expr {
  1
}""".strip()

    _test(script, expected)


def test_empty_braces():
    script = r"if {1} {}"
    _test(script, script, spaces_in_braces=False)

    expected = r"if { 1 } { }"
    _test(script, expected, spaces_in_braces=True)


def test_function_line_breaks():
    script = r"""
expr {
  max($a,
  $b, $c)
}""".strip()

    expected = r"""
expr {
  max($a,
    $b, $c)
}""".strip()

    _test(script, expected)

    script = r"""
expr {
  max(
  $a, $b, $c)
}""".strip()

    expected = r"""
expr {
  max(
    $a, $b, $c)
}""".strip()

    _test(script, expected)

    script = r"""
expr {
  max(
    $a, $b, $c
    )
}""".strip()

    expected = r"""
expr {
  max(
    $a, $b, $c
  )
}""".strip()

    _test(script, expected)


def test_paren_line_breaks():
    script = r"""
expr {
  (
  1 + 2 + 3
  )
}""".strip()

    expected = r"""
expr {
  (
    1 + 2 + 3
  )
}""".strip()

    _test(script, expected)


def test_if_else_newline_escape_indent():
    script = r"""
if { $cond } {
  puts "true"
} else \
{
  puts "false"
}"""

    expected = r"""
if { $cond } {
  puts "true"
} else \
  {
    puts "false"
  }""".strip()

    _test(script, expected)

    script = r"""
if { $cond } {
  puts "true"
} \
else \
{
  puts "false"
}""".strip()

    expected = r"""
if { $cond } {
  puts "true"
} \
  else \
  {
    puts "false"
  }""".strip()

    _test(script, expected)
