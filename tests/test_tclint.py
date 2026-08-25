import pathlib
import subprocess

import pytest

MY_DIR = pathlib.Path(__file__).parent.resolve()

tests = []
test_case_dir = MY_DIR / "data"
for path in test_case_dir.iterdir():
    if path.suffix == ".tcl" and path.with_suffix(".txt").exists():
        tests.append(str(path.relative_to(MY_DIR)))


@pytest.mark.parametrize("test", tests)
def test_tclint(test, tmp_path):
    """End-to-end tests."""
    output_path = (MY_DIR / test).with_suffix(".txt")
    with open(output_path, "r") as f:
        expected = f.read()

    # TODO: consider adding an --isolated flag that effectively implements this.
    default_config = tmp_path / "tclint.toml"
    with open(default_config, "w") as f:
        f.write("")

    cmd = ["tclint", test]
    # Prevents tclint from picking up the tclint.toml from tests/data.
    cmd += ["-c", default_config]

    p = subprocess.run(cmd, capture_output=True, cwd=MY_DIR)

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 0 if not expected else 1


def test_tclint_config_above(tmp_path):
    with open(tmp_path / "tclint.toml", "w") as f:
        f.write("ignore = ['command-args']")

    (tmp_path / "foo").mkdir()
    with open(tmp_path / "foo" / "foo.tcl", "w") as f:
        f.write("puts oh no, too many arguments")
    cmd = ["tclint", "."]

    p = subprocess.run(cmd, cwd=tmp_path / "foo")
    assert p.returncode == 0


def test_switches(tmp_path):
    test = (test_case_dir / "dirty.tcl").relative_to(MY_DIR)
    config_file = tmp_path / "tclint.toml"
    with open(config_file, "w") as f:
        f.write("ignore = ['unbraced-expr']")

    p = subprocess.run(
        [
            "tclint",
            "-c",
            config_file,
            "--style-line-length",
            "35",
            "--ignore",
            "",
            test,
        ],
        capture_output=True,
        cwd=MY_DIR,
    )

    expected = """
data/dirty.tcl:1:1: line length is 36, maximum allowed is 35 [line-length]
data/dirty.tcl:6:11: unnecessary command substitution within expression [redundant-expr]
data/dirty.tcl:6:17: expression with substitutions should be enclosed by braces [unbraced-expr]
""".lstrip()  # noqa E501

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 1


def test_special_file():
    p = subprocess.run(["tclint", "/dev/stdin"], input=b"")
    assert p.returncode == 0


def test_read_stdin():
    p = subprocess.Popen(
        ["tclint", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input="expr $foo".encode("utf-8"))

    output = stdout.decode("utf-8").strip()
    assert (
        output
        == "(stdin):1:6: expression with substitutions should be enclosed by braces"
        " [unbraced-expr]"
    )
    assert stderr == b""


def _run_stdin(source: str):
    p = subprocess.Popen(
        ["tclint", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input=source.encode("utf-8"))
    return stdout.decode("utf-8"), stderr.decode("utf-8")


def test_unknown_rule_keeps_the_token_the_user_wrote():
    """A space-separated list is invalid, but the warning must quote it verbatim.

    Stripping spaces before splitting on the comma joined the tokens into a
    name that appears nowhere in the source.
    """
    stdout, _ = _run_stdin("# tclint-disable unbraced-expr extra-junk\nexpr $foo\n")

    assert "unknown rule 'unbraced-expr extra-junk'" in stdout
    assert "rules must be comma-separated" in stdout
    assert "unbraced-exprextra-junk" not in stdout


def test_unknown_rule_without_whitespace_omits_the_comma_hint():
    """The hint is only useful when a missing comma is the likely cause."""
    stdout, _ = _run_stdin("# tclint-disable definitely-not-a-rule\nexpr $foo\n")

    assert "unknown rule 'definitely-not-a-rule'" in stdout
    assert "comma-separated" not in stdout


def test_spaces_around_comma_delimiter_still_parse():
    """Padding around the delimiter must keep working."""
    stdout, _ = _run_stdin(
        "# tclint-disable unbraced-expr , redundant-expr\nexpr { [expr $foo] }\n"
    )

    assert stdout == ""


def test_block_dynamic_plugin_config(tmp_path):
    plugin = """
print("plugin ran")
commands = {}
"""
    plugin_path = tmp_path / "dynamic.py"
    with open(plugin_path, "w") as f:
        f.write(plugin)

    config = f"commands = '{plugin_path}'"
    config_path = tmp_path / "config.toml"
    with open(config_path, "w") as f:
        f.write(config)

    # Validate setup can work
    p = subprocess.Popen(
        ["tclint", "--commands", plugin_path, "--trust-plugins", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
    )
    stdout, stderr = p.communicate()

    output = stdout.decode("utf-8").strip()
    assert output == "plugin ran"
    assert stderr == b""
    assert p.returncode == 0

    # Make sure dynamic plugin is blocked
    p = subprocess.Popen(
        ["tclint", "--config", config_path, "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=tmp_path,
    )
    stdout, stderr = p.communicate()

    output = stdout.decode("utf-8").strip()
    assert output.startswith("Warning: skipping untrusted plugin")
    assert "plugin ran" not in output
    assert p.returncode == 0
