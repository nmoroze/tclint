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


def test_aligned_sets():
    """Test style.allow-aligned-sets"""
    script = """
set foo  0
set barx 1"""

    violations = lint(script, Config(style_allow_aligned_sets=False), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("spacing")

    violations = lint(script, Config(style_allow_aligned_sets=True), Path())
    assert len(violations) == 0


def test_accidental_return_expr():
    script = "return 5 + 2"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("command-args")


def test_ignore_path():
    script = "puts  bad_spacing"
    fake_path = Path("bad.tcl")
    violations = lint(script, Config(), fake_path)
    assert len(violations) == 1

    config = Config(ignore=[{"path": fake_path, "rules": [Rule("spacing")]}])
    violations = lint(script, config, fake_path)
    assert len(violations) == 0


def test_redefined_builtin():
    script = "proc puts {} {}"
    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule("redefined-builtin")


def test_no_indent_namespace_eval():
    script = """
namespace eval my_namespace {
puts "okay no indent here"
 puts "indent errors still caught though"
if {1} {
puts "including in blocks"
}
}
"""
    violations = lint(script, Config(style_indent_namespace_eval=False), Path())
    assert len(violations) == 2
    assert violations[0].id == Rule.INDENT
    assert violations[0].pos[0] == 4
    assert violations[1].id == Rule.INDENT
    assert violations[1].pos[0] == 6


def test_no_violation_multiline_expr():
    script = r"""
if {1 && \
    2} {}"""
    violations = lint(script, Config(), Path())
    assert len(violations) == 0


def test_spacing_multiline():
    script = r"""
foo asdf asdf \
    qwerty    qwerty"""

    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.SPACING
    assert violations[0].pos == (3, 11)


def test_spacing_multiline_expr():
    script = r"""
expr {$a ?
      $b  : $d}"""

    violations = lint(script, Config(), Path())
    assert len(violations) == 1
    assert violations[0].id == Rule.EXPR_FORMAT
    assert violations[0].pos == (3, 9)


def test_no_indent_violation_after_close_brace():
    """Regression test for https://github.com/nmoroze/tclint/issues/48."""
    script = r"""puts {
  Hello} ;# asdf"""

    violations = lint(script, Config(), Path())
    assert len(violations) == 0
