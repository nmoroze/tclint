from pathlib import Path

from tclint.tclint import lint
from tclint.config import Config
from tclint.violations import Rule


def test_cmd_args_in_sub():
    """Ensure command args get checked in cmd sub."""
    script = "[puts]"
    violations = lint(script, Config(), Path())

    assert len(violations) == 1
    assert violations[0].id == Rule("command-args")


def test_no_false_positive_arg_expansion():
    """Ensure that argument count checks don't flag when the number of arguments
    is ambiguous."""
    # $foo may be a list with two items, which is legal
    script = "rename {*}$foo"
    violations = lint(script, Config(), Path())
    assert len(violations) == 0


def test_accidental_return_expr():
    script = "return 5 + 2"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("command-args")


def test_ignore_path():
    script = "expr $foo"
    fake_path = Path("bad.tcl")
    violations = lint(script, Config(), fake_path)
    assert len(violations) == 1

    config = Config(ignore=[{"path": fake_path, "rules": [Rule("unbraced-expr")]}])
    violations = lint(script, config, fake_path)
    assert len(violations) == 0


def test_redefined_builtin():
    script = "proc puts {} {}"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("redefined-builtin")
    assert violations[0].start == (1, 1)
    assert violations[0].end == (1, 13)


def test_no_violation_multiline_expr():
    script = r"""
if {1 && \
    2} {}"""
    violations = lint(script, Config(), Path())
    assert len(violations) == 0


def test_unbraced_expr_varsub():
    script = r"expr $foo"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.UNBRACED_EXPR
    assert violations[0].start == (1, 6)
    assert violations[0].end == (1, 10)


def test_unbraced_expr_with_braced_word():
    script = r"expr 1 + {2}"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.UNBRACED_EXPR
    assert violations[0].start == (1, 6)
    assert violations[0].end == (1, 13)

    script = r'expr 1 + "2"'
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.UNBRACED_EXPR
    assert violations[0].start == (1, 6)
    assert violations[0].end == (1, 13)

    script = r"expr {1} + {2}"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.UNBRACED_EXPR
    assert violations[0].start == (1, 6)
    assert violations[0].end == (1, 15)


def test_redundant_expr_check():
    script = r"""
expr {[expr 1]}
expr {([expr 1] + [expr 2])}
expr {[expr 1] ? [expr 2] : [expr 3]}
expr {max([expr 1], [expr 2])}
""".strip()

    violations = lint(script, Config(), Path())
    assert len(violations) == 8
    assert all(v.id == Rule.REDUNDANT_EXPR for v in violations)

    assert violations[0].start == (1, 7)
    assert violations[0].end == (1, 15)
    assert violations[1].start == (2, 8)
    assert violations[1].end == (2, 16)
    assert violations[2].start == (2, 19)
    assert violations[2].end == (2, 27)
    assert violations[3].start == (3, 7)
    assert violations[3].end == (3, 15)
    assert violations[4].start == (3, 18)
    assert violations[4].end == (3, 26)
    assert violations[5].start == (3, 29)
    assert violations[5].end == (3, 37)
    assert violations[6].start == (4, 11)
    assert violations[6].end == (4, 19)
    assert violations[7].start == (4, 21)
    assert violations[7].end == (4, 29)


def test_proc_args_bad():
    script = r"proc foo { { i 1 2 } } { }"
    violations = lint(script, Config(), Path())
    assert violations[0].id == Rule("command-args")


def test_expr_no_args():
    script = "expr"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("command-args")


def test_proc_no_args():
    script = "proc"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("command-args")
