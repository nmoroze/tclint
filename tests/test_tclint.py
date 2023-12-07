import pathlib
import subprocess

import pytest

MY_DIR = pathlib.Path(__file__).parent.resolve()

tests = []
test_case_dir = MY_DIR / "data"
for path in test_case_dir.iterdir():
    if path.suffix == ".tcl":
        tests.append(str(path.relative_to(MY_DIR)))


@pytest.mark.parametrize("test", tests)
def test_tclint(test):
    """End-to-end tests."""
    output_path = (MY_DIR / test).with_suffix(".txt")
    with open(output_path, "r") as f:
        expected = f.read()

    p = subprocess.run(["tclint", test], capture_output=True, cwd=MY_DIR)

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 0 if not expected else 1


def test_switches():
    test = (test_case_dir / "dirty.tcl").relative_to(MY_DIR)
    config_file = test_case_dir / "tclint.toml"

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
data/dirty.tcl:1:14: expected 1 space between words, got 2 [spacing]
data/dirty.tcl:1:36: line length is 36, maximum allowed is 35 [line-length]
data/dirty.tcl:2:1: expected indent of 2 spaces, got 0 [indent]
data/dirty.tcl:3:1: expected indent of 4 spaces, got 0 [indent]
data/dirty.tcl:4:1: expected indent of 2 spaces, got 0 [indent]
data/dirty.tcl:4:2: expected 1 space between words, got 3 [spacing]
data/dirty.tcl:5:1: expected indent of 4 spaces, got 8 [indent]
data/dirty.tcl:6:1: expected indent of 2 spaces, got 0 [indent]
data/dirty.tcl:7:1: expected indent of 4 spaces, got 8 [indent]
data/dirty.tcl:7:13: expected 1 space between words, got 3 [spacing]
data/dirty.tcl:8:1: expected indent of 2 spaces, got 4 [indent]
data/dirty.tcl:9:1: expected indent of 4 spaces, got 8 [indent]
data/dirty.tcl:9:13: expected 1 space between words, got 5 [spacing]
data/dirty.tcl:10:1: expected indent of 2 spaces, got 4 [indent]
""".lstrip()

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 1
