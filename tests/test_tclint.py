import os
import pathlib
import subprocess

import pytest

from tclint import tclint

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

    cmd = ["tclint", test]

    config_file = (MY_DIR / test).with_suffix(".toml")
    if config_file.exists():
        cmd += ["-c", config_file]

    p = subprocess.run(cmd, capture_output=True, cwd=MY_DIR)

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 0 if not expected else 1


def test_tclint_show_categories():
    test = (test_case_dir / "example.tcl").relative_to(MY_DIR)

    p = subprocess.run(
        [
            "tclint",
            "--show-categories",
            test,
        ],
        capture_output=True,
        cwd=MY_DIR,
    )
    expected = """
data/example.tcl:1:1: too many args for puts: got 4, expected no more than 3 [func:command-args]
data/example.tcl:2:1: expected indent of 0 spaces, got 2 [style:indent]
data/example.tcl:3:5: expected 1 space between words, got 3 [style:spacing]
""".lstrip()  # noqa E501

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 1


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
data/dirty.tcl:6:17: expression with substitutions should be enclosed by braces [unbraced-expr]
data/dirty.tcl:7:1: expected indent of 4 spaces, got 8 [indent]
data/dirty.tcl:7:13: expected 1 space between words, got 3 [spacing]
data/dirty.tcl:8:1: expected indent of 2 spaces, got 4 [indent]
data/dirty.tcl:9:1: expected indent of 4 spaces, got 8 [indent]
data/dirty.tcl:9:13: expected 1 space between words, got 5 [spacing]
data/dirty.tcl:10:1: expected indent of 2 spaces, got 4 [indent]
""".lstrip()  # noqa E501

    assert p.stdout.decode("utf-8") == expected
    assert p.returncode == 1


def test_special_file():
    p = subprocess.run(["tclint", "/dev/stdin"])
    assert p.returncode == 0


def test_read_stdin():
    p = subprocess.Popen(
        ["tclint", "-"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = p.communicate(input=' puts "hello world"'.encode("utf-8"))

    output = stdout.decode("utf-8").strip()
    assert output == "(stdin):1:1: expected indent of 0 spaces, got 1 [indent]"
    assert stderr == b""


def test_resolve_sources(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("a")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ignore").mkdir()
    (tmp_path / "src" / "ignore" / "bar.tcl").touch()
    (tmp_path / "src" / "ignore1.tcl").touch()
    (tmp_path / "src" / "ignore2.tcl").touch()
    to_include = tmp_path / "src" / "foo.tcl"
    to_include.touch()

    cwd = os.getcwd()
    os.chdir(tmp_path)

    extensions = ["tcl"]

    sources = tclint.resolve_sources(
        [pathlib.Path(".")],
        exclude_patterns=[
            # test bare pattern matches anywhere in tree
            "ignore",
            # test glob
            "ignore*.tcl",
            # test pattern with "/" only matches from root of tree
            "/foo.tcl",
        ],
        exclude_root=tmp_path,
        extensions=extensions,
    )

    assert len(sources) == 1
    assert sources[0] == to_include.relative_to(tmp_path)

    # test absolute path outside of exclude_root doesn't get matched by ignore
    # pattern starting with "/"
    other_dir = tmp_path_factory.mktemp("b")
    in_path = other_dir / "foo.tcl"
    in_path.touch()
    sources = tclint.resolve_sources(
        [in_path],
        exclude_patterns=[str(in_path)],
        exclude_root=tmp_path,
        extensions=extensions,
    )
    assert len(sources) == 1
    assert sources[0] == in_path

    # test that we can match outside of exclude root with explicit relative path
    top_src = tmp_path / "top.tcl"
    top_src.touch()
    sources = tclint.resolve_sources(
        [top_src],
        exclude_patterns=["../top.tcl"],
        exclude_root=tmp_path / "src",
        extensions=extensions,
    )
    assert len(sources) == 0

    # test auto-escape leading hash
    other_other_dir = tmp_path_factory.mktemp("c")
    hash_srcs = [other_other_dir / "#foo.tcl", other_other_dir / "#bar.tcl"]
    for src in hash_srcs:
        src.touch()
    sources = tclint.resolve_sources(
        hash_srcs,
        # extra space before #bar.tcl is important to make sure we don't just match ^#
        exclude_patterns=["#foo.tcl", " #bar.tcl"],
        exclude_root=other_other_dir,
        extensions=extensions,
    )
    assert len(sources) == 0

    os.chdir(cwd)


def test_resolve_sources_extensions(tmp_path):
    foo_file = tmp_path / "file.foo"
    foo_file.touch()
    bar_file = tmp_path / "file.BAR"
    bar_file.touch()

    cwd = os.getcwd()
    os.chdir(tmp_path)

    sources = tclint.resolve_sources(
        [tmp_path], exclude_patterns=[], exclude_root=tmp_path, extensions=["foo"]
    )
    assert len(sources) == 1
    assert sources[0] == foo_file

    sources = tclint.resolve_sources(
        [tmp_path], exclude_patterns=[], exclude_root=tmp_path, extensions=["bar"]
    )
    assert len(sources) == 1
    assert sources[0] == bar_file

    os.chdir(cwd)
