from tclint.tclint import lint
from tclint.config import Config


def test_cmd_args_in_sub():
    """Ensure command args get checked in cmd sub."""
    script = "[puts]"
    violations = lint(script, Config())

    assert len(violations) == 1
    assert violations[0].id == "command-args"


def test_no_false_positive_arg_expansion():
    """Ensure that argument count checks don't flag when the number of arguments
    is ambiguous."""
    # $foo may be a list with two items, which is legal
    script = "rename {*}$foo"
    violations = lint(script, Config())
    assert len(violations) == 0


def test_aligned_sets():
    """Test style.allow-aligned-sets"""
    script = """
set foo  0
set barx 1"""

    violations = lint(script, Config(style_aligned_set=False))
    assert len(violations) == 1
    assert violations[0].id == "spacing"

    violations = lint(script, Config(style_aligned_set=True))
    assert len(violations) == 0


def test_accidental_return_expr():
    script = "return 5 + 2"
    violations = lint(script, Config())
    assert len(violations) == 1
    assert violations[0].id == "command-args"
