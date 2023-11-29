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
