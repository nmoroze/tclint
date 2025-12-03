"""End-to-end tests for tclfmt."""

import pathlib
import shutil
import subprocess

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_tclfmt(tmp_path):
    # Ensure that tclfmt doesn't pick up tclint.toml from tests directory.
    # TODO: consider adding an --isolated flag that effectively implements this.
    default_config = tmp_path / "tclint.toml"
    with open(default_config, "w") as f:
        f.write("")

    cmd = ["tclfmt", MY_DIR / "data" / "dirty.tcl", "-c", default_config]
    p = subprocess.run(cmd, capture_output=True, cwd=MY_DIR)

    with open(MY_DIR / "data" / "dirty.formatted.tcl", "r") as f:
        expected = f.read()

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 0


def test_tclfmt_check():
    cmd = ["tclfmt", "--check", MY_DIR / "data" / "dirty.tcl"]
    p = subprocess.run(cmd, capture_output=True, cwd=MY_DIR)

    assert p.returncode == 1


def test_tclfmt_in_place(tmp_path):
    test_data = MY_DIR / "data" / "dirty.tcl"
    input = tmp_path / "dirty.tcl"
    shutil.copyfile(test_data, input)

    cmd = ["tclfmt", "--in-place", input]
    p = subprocess.run(cmd, capture_output=True, cwd=MY_DIR)

    with open(input, "r") as f:
        actual = f.read()

    with open(MY_DIR / "data" / "dirty.formatted.tcl", "r") as f:
        expected = f.read()

    assert p.returncode == 0
    assert actual == expected


def test_tclfmt_partial():
    script = r"""
    puts "foo"
      puts "bar"
"""
    expected = r"""
    puts "foo"
    puts "bar"
"""
    p = subprocess.Popen(
        ["tclfmt", "--partial", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input=script.encode("utf-8"))

    output = stdout.decode("utf-8")
    assert output == expected
    assert stderr == b""
