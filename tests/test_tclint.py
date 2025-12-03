import os
import pathlib
import subprocess

import pytest

from tclint.cli.utils import Resolver
from tclint import config

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


def test_resolve_sources(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("a")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "ignore").mkdir()
    (tmp_path / "src" / "ignore" / "bar.tcl").touch()
    (tmp_path / "src" / "ignore1.tcl").touch()
    (tmp_path / "src" / "ignore2.tcl").touch()
    to_include = tmp_path / "src" / "foo.tcl"
    to_include.touch()

    resolver = Resolver(
        global_config=config.Config(
            exclude=[
                # test bare pattern matches anywhere in tree
                config.ExcludePattern("ignore", tmp_path),
                # test glob
                config.ExcludePattern("ignore*.tcl", tmp_path),
                # test pattern with "/" only matches from root of tree
                config.ExcludePattern("/foo.tcl", tmp_path),
            ],
        )
    )
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    assert sources[0][0] == to_include

    # test absolute path outside of exclude_root doesn't get matched by ignore
    # pattern starting with "/"
    other_dir = tmp_path_factory.mktemp("b")
    in_path = other_dir / "foo.tcl"
    in_path.touch()
    resolver = Resolver(
        global_config=config.Config(
            exclude=[config.ExcludePattern(str(in_path), tmp_path)],
        )
    )
    sources = resolver.resolve_sources([in_path], tmp_path)
    assert len(sources) == 1
    assert sources[0][0] == in_path

    # test that we can match outside of exclude root with explicit relative path
    top_src = tmp_path / "top.tcl"
    top_src.touch()
    resolver = Resolver(
        global_config=config.Config(
            exclude=[config.ExcludePattern("../top.tcl", tmp_path / "src")],
        )
    )
    sources = resolver.resolve_sources([top_src], tmp_path)
    assert len(sources) == 0

    # test auto-escape leading hash
    other_other_dir = tmp_path_factory.mktemp("c")
    hash_srcs = [other_other_dir / "#foo.tcl", other_other_dir / "#bar.tcl"]
    for src in hash_srcs:
        src.touch()
    resolver = Resolver(
        global_config=config.Config(
            exclude=[
                config.ExcludePattern("#foo.tcl", other_other_dir),
                config.ExcludePattern(" #bar.tcl", other_other_dir),
            ],
        )
    )
    sources = resolver.resolve_sources(hash_srcs, tmp_path)
    assert len(sources) == 0


def test_resolve_sources_extensions(tmp_path):
    foo_file = tmp_path / "file.foo"
    foo_file.touch()
    bar_file = tmp_path / "file.BAR"
    bar_file.touch()

    cwd = os.getcwd()
    os.chdir(tmp_path)

    resolver = Resolver(global_config=config.Config(extensions=["foo"]))
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    assert sources[0][0] == foo_file

    resolver = Resolver(global_config=config.Config(extensions=["bar"]))
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    assert sources[0][0] == bar_file

    os.chdir(cwd)


def test_resolve_sources_multiple_roots(tmp_path):
    bar = tmp_path / "bar.tcl"
    baz = tmp_path / "baz.tcl"
    (tmp_path / "foo").mkdir()
    foo_bar = tmp_path / "foo" / "bar.tcl"
    foo_baz = tmp_path / "foo" / "baz.tcl"

    sources = []
    for source in (bar, baz, foo_bar, foo_baz):
        source.touch()
        sources.append(source)

    resolver = Resolver(
        global_config=config.Config(
            exclude=[
                config.ExcludePattern("/bar.tcl", tmp_path),
                config.ExcludePattern("/baz.tcl", tmp_path / "foo"),
            ],
        )
    )
    resolved = resolver.resolve_sources(sources, tmp_path)
    assert set(path for path, _ in resolved) == set([baz, foo_bar])

    resolver = Resolver(
        global_config=config.Config(
            exclude=[
                config.ExcludePattern("/baz.tcl", tmp_path),
                config.ExcludePattern("/bar.tcl", tmp_path / "foo"),
            ],
        )
    )
    resolved = resolver.resolve_sources(sources, tmp_path)
    assert set(path for path, _ in resolved) == set([bar, foo_baz])


def test_resolve_sources_multiple_configs(tmp_path):
    """Test setup with several config files in source tree that affect traversal
    behavior."""

    # Constructs the following:
    # /
    #   foo/
    #     tclint.toml: exclude=["bar"]
    #     bar/
    #       foobar.tcl
    #     baz/
    #       tclint.toml: extensions = ["myext"]
    #       foobaz.tcl
    #       foobaz.myext
    (tmp_path / "foo").mkdir()
    with open(tmp_path / "foo" / "tclint.toml", "w") as f:
        f.write("exclude = ['bar']")

    (tmp_path / "foo" / "bar").mkdir()
    (tmp_path / "foo" / "bar" / "foobar.tcl").touch()

    (tmp_path / "foo" / "baz").mkdir()
    with open(tmp_path / "foo" / "baz" / "tclint.toml", "w") as f:
        f.write("extensions = ['myext']")
    (tmp_path / "foo" / "baz" / "foobaz.tcl").touch()
    (tmp_path / "foo" / "baz" / "foobaz.myext").touch()

    # Running from the root, we expect to only see foobaz.myext. foo/tclint.toml's
    # exclude prevents traversal of foo/bar, and foo/baz/tclint.toml affects the
    # extensions used for resolving under foo/baz.
    resolver = Resolver()
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    src, cfg = sources[0]
    assert src == tmp_path / "foo" / "baz" / "foobaz.myext"
    assert cfg.extensions == ["myext"]

    # Even if we select foobar.tcl explicitly, foo/bar/tclint.toml's exclude still takes
    # effect.
    resolver = Resolver()
    sources = resolver.resolve_sources(
        [tmp_path / "foo" / "bar" / "foobar.tcl"], tmp_path
    )
    assert len(sources) == 0

    # Add a bit of a twist!
    with open(tmp_path / "foo" / "bar" / "tclint.toml", "w") as f:
        f.write("exclude = []")

    # Running from root, there's no difference - foo/tclint.toml still prevents
    # traversal of foo/bar.
    resolver = Resolver()
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    src, cfg = sources[0]
    assert src == tmp_path / "foo" / "baz" / "foobaz.myext"
    assert cfg.extensions == ["myext"]

    # However, if the file is explicitly specified, then its config file (with the
    # nullified exclude) is picked up.
    resolver = Resolver()
    sources = resolver.resolve_sources(
        [tmp_path / "foo" / "bar" / "foobar.tcl"], tmp_path
    )
    assert len(sources) == 1
    src, cfg = sources[0]
    assert src == tmp_path / "foo" / "bar" / "foobar.tcl"
    assert cfg.exclude == []

    # If we have a global config, ignore all the config files in-tree.
    resolver = Resolver(
        global_config=config.Config(ignore=[config.Rule("unbraced-expr")])
    )
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 2
    assert set(path for path, _ in sources) == set([
        tmp_path / "foo" / "bar" / "foobar.tcl", tmp_path / "foo" / "baz" / "foobaz.tcl"
    ])
    for _, cfg in sources:
        assert cfg.ignore == [config.Rule("unbraced-expr")]


def test_resolve_pyproject_subdirectory(tmp_path):
    (tmp_path / "foo").mkdir()
    with open(tmp_path / "foo" / "pyproject.toml", "w") as f:
        f.write("""[tool.tclint]
        ignore = ["unbraced-expr"]""")
    (tmp_path / "foo" / "foo.tcl").touch()

    resolver = Resolver()
    sources = resolver.resolve_sources([tmp_path], tmp_path)
    assert len(sources) == 1
    src, cfg = sources[0]
    assert src == tmp_path / "foo" / "foo.tcl"
    assert cfg.ignore == [config.Rule("unbraced-expr")]


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
        ["tclint", "--commands", plugin_path, "-"],
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
    assert output.startswith("Invalid config file")
    assert "dynamic plugins cannot be specified via config file" in output
    assert p.returncode > 0
