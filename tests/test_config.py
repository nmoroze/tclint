import argparse
import pathlib

import pytest

from tclint.config import (
    Config,
    ConfigError,
    ExcludePattern,
    SpacesInBraces,
    setup_config_cli_args,
    setup_tclfmt_config_cli_args,
)
from tclint.violations import Rule

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_example_config():
    config_path = MY_DIR / "data" / "tclint.toml"
    cwd = pathlib.Path.cwd()
    config = Config.from_path(config_path, cwd)

    assert config.exclude == [
        ExcludePattern("ignore_me/", cwd),
        ExcludePattern("ignore*.tcl", cwd),
        ExcludePattern("/ignore_from_here", cwd),
    ]
    assert config.ignore == [Rule("unbraced-expr")]
    assert config.extensions == ["tcl"]

    # Depending on whether this file happens to exist on the test runner's computer,
    # this may be the string that appears in the config, or a Path with the user
    # resolved.
    assert len(config.commands) == 1
    assert str(config.commands[0]).endswith(".tclint/openroad.json")

    assert config.style_indent == 2
    assert config.style_line_length == 80
    assert config.style_indent_namespace_eval is False
    assert config.style_spaces_in_braces == SpacesInBraces.ALWAYS
    assert config.style_emacs is True


def test_invalid_rule():
    with pytest.raises(ConfigError) as excinfo:
        Config.from_dict({"ignore": ["asdf"]}, pathlib.Path.cwd())

    if excinfo is not None:
        print(str(excinfo.value))


def test_pyproject():
    config = Config.from_pyproject(MY_DIR / "data")
    assert config.style_indent == 2
    assert config.ignore == [Rule("unbraced-expr")]


def test_tclint_config_args():
    parser = argparse.ArgumentParser("tclint")
    cwd = pathlib.Path.cwd()
    setup_config_cli_args(parser, cwd)

    args = [
        "--ignore",
        "unbraced-expr, line-length",
        "--extend-ignore",
        "trailing-whitespace",
        "--exclude",
        "my_dir,my_file",
        "--extend-exclude",
        "extend_to_file",
        "--extensions",
        "sdc, exp",
        "--commands",
        "commands.json",
        "--style-line-length",
        "79",
    ]

    args = parser.parse_args(args)

    assert args.ignore == [Rule("unbraced-expr"), Rule("line-length")]
    assert args.extend_ignore == [Rule("trailing-whitespace")]
    assert args.exclude == [
        ExcludePattern("my_dir", cwd),
        ExcludePattern("my_file", cwd),
    ]
    assert args.extend_exclude == [ExcludePattern("extend_to_file", cwd)]
    assert args.extensions == ["sdc", "exp"]
    assert len(args.commands) == 1
    assert str(args.commands[0]).endswith("commands.json")
    assert args.style_line_length == 79


def test_tclfmt_config_args():
    parser = argparse.ArgumentParser("tclfmt")
    cwd = pathlib.Path.cwd()
    setup_tclfmt_config_cli_args(parser, cwd)

    args = [
        "--exclude",
        "my_dir,my_file",
        "--extend-exclude",
        "extend_to_file",
        "--extensions",
        "sdc, exp",
        "--commands",
        "commands.json",
        "--indent",
        "5",
        "--max-blank-lines",
        "4",
        "--indent-namespace-eval",
        "--no-spaces-in-braces",
    ]

    args = parser.parse_args(args)

    assert args.exclude == [
        ExcludePattern("my_dir", cwd),
        ExcludePattern("my_file", cwd),
    ]
    assert args.extend_exclude == [ExcludePattern("extend_to_file", cwd)]
    assert args.extensions == ["sdc", "exp"]
    assert len(args.commands) == 1
    assert args.commands[0].endswith("commands.json")
    assert args.style_indent == 5
    assert args.style_max_blank_lines == 4
    assert args.style_indent_namespace_eval is True
    assert args.style_spaces_in_braces == SpacesInBraces.NEVER


def test_invalid_tclint_args():
    parser = argparse.ArgumentParser("tclint", exit_on_error=False)
    setup_config_cli_args(parser, pathlib.Path.cwd())

    for arg, value in [
        ("--ignore", "unbraced-expr, line-length, invalid-rule"),
        ("--extend-ignore", "trailing-whitespace, invalid-rule"),
        ("--style-line-length", "asdf"),
    ]:
        with pytest.raises(argparse.ArgumentError) as excinfo:
            parser.parse_args([arg, value])

        # For manually auditing error messages
        print(excinfo.value)


def test_invalid_tclfmt_args():
    parser = argparse.ArgumentParser("tclfmt", exit_on_error=False)
    setup_tclfmt_config_cli_args(parser, pathlib.Path.cwd())

    for arg, value in [
        ("--indent", "qwerty"),
        ("--max-blank-lines", "uiop"),
    ]:
        with pytest.raises(argparse.ArgumentError) as excinfo:
            parser.parse_args([arg, value])

        # For manually auditing error messages
        print(excinfo.value)


def test_invalid_config():
    for config in [
        {"ignore": ["unbraced-expr", "invalid-rule", "line-length"]},
        {"commands": 1},
        {"style": {"indent": "abc"}},
        {"style": {"line-length": "def"}},
        {"style": {"max-blank-lines": "ghi"}},
        {"style": {"indent-namespace-eval": "not-a-bool"}},
        {"style": {"spaces-in-braces": -1}},
        {"extra-key": "value"},
    ]:
        with pytest.raises(ConfigError) as excinfo:
            Config.from_dict(config, pathlib.Path.cwd())

        # For manually auditing error messages
        print(excinfo.value)


def test_config_relative_paths(tmp_path):
    """Make sure relative paths in config get resolved."""
    config = """
exclude = ["/foo.tcl"]
commands = "commands.json"
"""

    config_path = tmp_path / "tclint.toml"

    with open(config_path, "w") as f:
        f.write(config)

    with open(tmp_path / "commands.json", "w") as f:
        f.write(r"{}")

    config = Config.from_path(config_path, tmp_path)
    assert config.exclude == [ExcludePattern("/foo.tcl", tmp_path)]
    assert config.commands == [tmp_path / "commands.json"]
    assert config.ignore == []
