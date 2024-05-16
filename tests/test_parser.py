import pathlib

import pytest

from tclint.parser import (
    Parser,
    Script,
    Command,
    Comment,
    CommandSub,
    ArgExpansion,
    BareWord,
    CompoundBareWord,
    QuotedWord,
    BracedWord,
    VarSub,
    List,
    BracedExpression,
    Expression,
    BinaryOp,
    TernaryOp,
    Function,
    TclSyntaxError,
)

MY_DIR = pathlib.Path(__file__).parent.resolve()


def parse(input):
    parser = Parser(debug=True)
    return parser.parse(input)


def test_null():
    script = ""
    tree = parse(script)
    assert tree == Script()


def test_escaped_brace():
    script = r"puts {Dinosaur dan\} {asdf}}"
    tree = parse(script)
    assert tree == Script(
        Command(BareWord("puts"), BracedWord(r"Dinosaur dan\} {asdf}"))
    )


def test_comments():
    script = r"""# lonely comment
    puts "hello"; # comment after command
    # multiline \
    comment
    # comment over \\
    puts "goodbye"
    # comment with a semicolon; hello"""
    tree = parse(script)
    assert tree == Script(
        Comment(" lonely comment"),
        Command(BareWord("puts"), QuotedWord(BareWord("hello"))),
        Comment(" comment after command"),
        Comment(" multiline \\\n    comment"),
        Comment(" comment over \\\\"),
        Command(BareWord("puts"), QuotedWord(BareWord("goodbye"))),
        Comment(" comment with a semicolon; hello"),
    )


def test_proc_in_proc():
    script = """proc proc_in_proc {} {
      proc asdf {} {
        puts "Hello world"
      }
    }"""
    tree = parse(script)

    assert tree == Script(
        Command(
            BareWord("proc"),
            BareWord("proc_in_proc"),
            BracedWord(""),
            Script(
                Command(
                    BareWord("proc"),
                    BareWord("asdf"),
                    BracedWord(""),
                    Script(
                        Command(BareWord("puts"), QuotedWord(BareWord("Hello world"))),
                    ),
                ),
            ),
        )
    )

    outer_proc = tree.children[0]
    inner_proc = outer_proc.args[2].children[0]
    puts_cmd = inner_proc.args[2].children[0]

    assert outer_proc.line == 1
    assert inner_proc.line == 2
    assert puts_cmd.line == 3


def test_arg_expansion():
    script = "puts {*}{foo bar baz}; {*}  "
    tree = parse(script)
    assert tree == Script(
        Command(BareWord("puts"), ArgExpansion(BracedWord("foo bar baz"))),
        Command(BracedWord("*")),
    )


def test_weird_code_block():
    """Test that } that appears to be in comment actually terminates body of
    proc."""

    script = """proc foo {} {
        # bar }
        puts baz
    }"""

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("proc"),
            BareWord("foo"),
            BracedWord(""),
            Script(Comment(" bar ")),
        ),
        Command(BareWord("puts"), BareWord("baz")),
        Command(BareWord("}")),
    )


def test_var_sub():
    # TODO: test backslash sub in var name?
    script = r"""puts "Hello $name"
    puts prefix-$suffix
    puts $hElLo__h0w::areyou:::
    puts $:
    puts ${as"{]$l}"""

    tree = parse(script)
    assert tree == Script(
        Command(BareWord("puts"), QuotedWord(BareWord("Hello "), VarSub("name"))),
        Command(
            BareWord("puts"),
            CompoundBareWord(BareWord("prefix-"), VarSub("suffix")),
        ),
        Command(BareWord("puts"), VarSub("hElLo__h0w::areyou:::")),
        Command(BareWord("puts"), BareWord("$:")),
        Command(BareWord("puts"), VarSub('as"{]$l')),
    )


def test_fancy_var_sub():
    script = "$name([calculate index]-middle-$suffix)"
    tree = parse(script)
    assert tree == Script(
        Command(
            VarSub(
                "name",
                CommandSub(Command(BareWord("calculate"), BareWord("index"))),
                BareWord("-middle-"),
                VarSub("suffix"),
            )
        )
    )


def test_command_sub():
    script = r'"hello [puts {[} [nested \] command]]"'
    tree = parse(script)
    assert tree == Script(
        Command(
            QuotedWord(
                BareWord("hello "),
                CommandSub(
                    Command(
                        BareWord("puts"),
                        BracedWord("["),
                        CommandSub(
                            Command(
                                BareWord("nested"),
                                BareWord("\\]"),
                                BareWord("command"),
                            )
                        ),
                    )
                ),
            )
        )
    )


def test_weird_words():
    script = r"""puts "hello {{}"
    puts h"llo
    puts h}{llo"""
    tree = parse(script)
    assert tree == Script(
        Command(BareWord("puts"), QuotedWord(BareWord(r"hello {{}"))),
        Command(BareWord("puts"), BareWord(r'h"llo')),
        Command(BareWord("puts"), BareWord(r"h}{llo")),
    )


def test_multiline():
    script = r'''puts "Multiline \
    Word"'''
    tree = parse(script)

    # The \\n\s+ doesn't get subbed for a space, but that should be okay. The
    # right thing happens with argument parsing, and we don't have anything else
    # that interprets values of words.

    assert tree == Script(
        Command(BareWord("puts"), QuotedWord(BareWord("Multiline \\\n    Word")))
    )


def test_multiline_braces():
    script = r"""if {1} {
        cmd arg1 \
            arg2 \
            arg3
        }"""
    tree = parse(script)

    assert tree == Script(
        Command(
            BareWord("if"),
            BracedExpression(BareWord("1")),
            Script(
                Command(
                    BareWord("cmd"),
                    BareWord("arg1"),
                    BareWord("arg2"),
                    BareWord("arg3"),
                )
            ),
        )
    )


def test_clean_tcl():
    with open(MY_DIR / "data" / "clean.tcl", "r") as f:
        script = f.read()
    tree = parse(script)

    assert tree == Script(
        Command(
            BareWord("for"),
            Script(Command(BareWord("set"), BareWord("i"), BareWord("1"))),
            BracedExpression(
                BinaryOp(
                    VarSub("i"),
                    BareWord("<"),
                    BareWord("100"),
                ),
            ),
            Script(Command(BareWord("incr"), BareWord("i"))),
            Script(
                Command(
                    BareWord("if"),
                    BracedExpression(
                        BinaryOp(
                            VarSub("i"),
                            BareWord("%"),
                            BinaryOp(
                                BareWord("15"),
                                BareWord("=="),
                                BareWord("0"),
                            ),
                        ),
                    ),
                    Script(
                        Command(BareWord("puts"), QuotedWord(BareWord("FizzBuzz"))),
                    ),
                    BareWord("elseif"),
                    BracedExpression(
                        BinaryOp(
                            VarSub("i"),
                            BareWord("%"),
                            BinaryOp(
                                BareWord("3"),
                                BareWord("=="),
                                BareWord("0"),
                            ),
                        ),
                    ),
                    Script(
                        Command(BareWord("puts"), QuotedWord(BareWord("Fizz"))),
                    ),
                    BareWord("elseif"),
                    BracedExpression(
                        BinaryOp(
                            VarSub("i"),
                            BareWord("%"),
                            BinaryOp(
                                BareWord("5"),
                                BareWord("=="),
                                BareWord("0"),
                            ),
                        ),
                    ),
                    Script(
                        Command(BareWord("puts"), QuotedWord(BareWord("Buzz"))),
                    ),
                    BareWord("else"),
                    Script(
                        Command(BareWord("puts"), VarSub("i")),
                    ),
                ),
            ),
        ),
    )


def test_line_numbers():
    script = r"""# line 1
    # line 2
    if {1} {
        # line 4
    }
    # line 6
    """
    tree = parse(script)
    assert tree.children[0].line == 1
    assert tree.children[0].col == 1
    assert tree.children[1].line == 2
    # weird col numbers on account of extra spaces in multiline string
    assert tree.children[1].col == 5
    if_cmd = tree.children[2]
    if_body = if_cmd.children[2]
    assert if_body.children[0].line == 4
    assert if_body.children[0].col == 9
    assert tree.children[3].line == 6

    # col 5 b/c of extra whitespace in multiline string
    assert tree.end_pos == (7, 5)


def test_syntax_error():
    script = 'puts "hello'
    with pytest.raises(TclSyntaxError):
        parse(script)


def test_switch():
    script = r"""switch -regexp $foo { "a" {
            puts "a"
        }
        "b" {
            puts "b"
        }
    }"""

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("switch"),
            BareWord("-regexp"),
            VarSub("foo"),
            List(
                QuotedWord(BareWord("a")),
                Script(
                    Command(BareWord("puts"), QuotedWord(BareWord("a"))),
                ),
                QuotedWord(BareWord("b")),
                Script(
                    Command(BareWord("puts"), QuotedWord(BareWord("b"))),
                ),
            ),
        )
    )

    # test positions - this has been tricky
    assert tree.children[0].children[3].children[0].col == 23
    assert tree.children[0].children[3].children[1].children[0].line == 2


def test_other_switch():
    script = r'switch $switchopt -- $foo "a" "puts a" "b" "puts b"'

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("switch"),
            VarSub("switchopt"),
            BareWord("--"),
            VarSub("foo"),
            QuotedWord(BareWord("a")),
            Script(
                Command(BareWord("puts"), BareWord("a")),
            ),
            QuotedWord(BareWord("b")),
            Script(
                Command(BareWord("puts"), BareWord("b")),
            ),
        )
    )


def test_puts_blank():
    script = 'puts ""'

    tree = parse(script)
    assert tree == Script(Command(BareWord("puts"), QuotedWord()))


def test_eval_positions():
    script = r"""eval  command  arg1\
 arg2"""

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("eval"),
            Script(Command(BareWord("command"), BareWord("arg1"), BareWord("arg2"))),
        )
    )
    eval_command = tree.children[0]
    script = eval_command.args[0]
    command = script.children[0]
    assert command.children[0].pos == (1, 7)
    assert command.children[1].pos == (1, 16)
    assert command.children[2].pos == (2, 2)


def test_eval_braced_multi_arg():
    script = "eval puts {a b c}"

    tree = parse(script)
    assert tree == Script(
        Command(BareWord("eval"), BareWord("puts"), BracedWord("a b c"))
    )

    # This reflects the actual Tcl semantics, but we currently treat this as
    # un-parseable since we don't have a clean way to handle the positions of these
    # items for style-checking purposes.
    # assert tree == Script(
    #     Command(
    #         BareWord("eval"),
    #         Script(
    #             Command(BareWord("puts"), BareWord("a"), BareWord("b"), BareWord("c"))
    #         ),
    #     )
    # )


def test_eval():
    script = "eval {puts {a b c}}"

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("eval"), Script(Command(BareWord("puts"), BracedWord("a b c")))
        )
    )


def test_dict_for():
    script = r"""dict for {key value} mydict {
        puts "$key $value"
    }"""

    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("dict"),
            BareWord("for"),
            BracedWord("key value"),
            BareWord("mydict"),
            Script(
                Command(
                    BareWord("puts"),
                    QuotedWord(VarSub("key"), BareWord(" "), VarSub("value")),
                ),
            ),
        )
    )


def test_eval_lines():
    script = r"""namespace eval my_namespace {
        puts "asdf"
    }"""

    tree = parse(script)
    puts_cmd = tree.children[0].children[3].children[0]
    assert puts_cmd.line == 2


def test_recursive_parse_in_cmd_sub():
    script = "[catch {analyze_power_grid -net $net -corner $corner} err]"
    tree = parse(script)

    assert tree == Script(
        Command(
            CommandSub(
                Command(
                    BareWord("catch"),
                    Script(
                        Command(
                            BareWord("analyze_power_grid"),
                            BareWord("-net"),
                            VarSub("net"),
                            BareWord("-corner"),
                            VarSub("corner"),
                        )
                    ),
                    BareWord("err"),
                )
            )
        )
    )


def test_parse_list():
    val = "alpha beta gamma"
    node = BracedWord(val, pos=(1, 1), end_pos=(1, 1 + len(val)))
    parser = Parser(debug=True)
    list_node = parser.parse_list(node)
    assert list_node.children == [
        BareWord("alpha"),
        BareWord("beta"),
        BareWord("gamma"),
    ]


def test_expr_simple():
    """A single word without substitution should parse properly as an expression
    even without braces."""
    script = 'expr "5"'
    tree = parse(script)
    assert tree == Script(Command(BareWord("expr"), Expression(BareWord("5"))))


def test_expr_sub_brace():
    script = "expr {int($foo)}"
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            BracedExpression(Function(BareWord("int"), VarSub("foo"))),
        )
    )


def test_expr_sub_no_brace():
    """Since this isn't wrapped in {...}, should silently parse as normal Tcl.

    (flagging the fact it's not being parsed as an expr would get handled by a
    separate lint check)
    """
    script = "expr int($foo)"
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            CompoundBareWord(BareWord("int("), VarSub("foo"), BareWord(")")),
        )
    )


def test_expr_finite_check():
    """From bottom of https://wiki.tcl-lang.org/page/Inf."""
    script = "expr {[string is double -strict $x] && $x == $x && $x + 1 != $x}"
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            BracedExpression(
                BinaryOp(
                    CommandSub(
                        Command(
                            BareWord("string"),
                            BareWord("is"),
                            BareWord("double"),
                            BareWord("-strict"),
                            VarSub("x"),
                        )
                    ),
                    BareWord("&&"),
                    BinaryOp(
                        VarSub("x"),
                        BareWord("=="),
                        BinaryOp(
                            VarSub("x"),
                            BareWord("&&"),
                            BinaryOp(
                                VarSub("x"),
                                BareWord("+"),
                                BinaryOp(BareWord("1"), BareWord("!="), VarSub("x")),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def test_expr_newline():
    """Mostly meant to test backslash newline, also sneaks in ternary, different
    word types, and indexed varsub."""
    script = r"""expr {"conditional" ? $::env(FOO) : \
        {foo}}"""
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            BracedExpression(
                TernaryOp(
                    QuotedWord(BareWord("conditional")),
                    BareWord("?"),
                    VarSub("::env", BareWord("FOO")),
                    BareWord(":"),
                    BracedWord("foo"),
                ),
            ),
        )
    )


def test_expr_no_spaces_binop():
    script = "expr {1-1}; expr {1eq1};"
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            BracedExpression(BinaryOp(BareWord("1"), BareWord("-"), BareWord("1"))),
        ),
        Command(
            BareWord("expr"),
            BracedExpression(BinaryOp(BareWord("1"), BareWord("eq"), BareWord("1"))),
        ),
    )


def test_newline_in_expr():
    script = """expr {$foo eq "foo" &&
        $bar eq "bar"}"""
    tree = parse(script)
    assert tree == Script(
        Command(
            BareWord("expr"),
            BracedExpression(
                BinaryOp(
                    VarSub("foo"),
                    BareWord("eq"),
                    BinaryOp(
                        QuotedWord(BareWord("foo")),
                        BareWord("&&"),
                        BinaryOp(
                            VarSub("bar"),
                            BareWord("eq"),
                            QuotedWord(BareWord("bar")),
                        ),
                    ),
                ),
            ),
        )
    )


def test_subparsed_positions():
    script = r"""if {1} pwd
if 1 {
    pwd
}"""
    tree = parse(script)

    if0 = tree.children[0]
    if0_expr = if0.args[0]
    if0_expr_inner = if0_expr.children[0]
    assert if0_expr_inner.pos == (1, 5)
    if0_body = if0.args[1]
    if0_body_inner = if0_body.children[0]
    assert if0_body_inner.pos == (1, 8)

    if1 = tree.children[1]
    if1_expr = if1.args[0]
    if1_expr_inner = if1_expr.children[0]
    assert if1_expr_inner.pos == (2, 4)
    if1_body = if1.args[1]
    if1_body_inner = if1_body.children[0]
    assert if1_body_inner.pos == (3, 5)
