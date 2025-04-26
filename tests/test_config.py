import argparse
import pathlib

import pytest

from tclint.config import (
    get_config,
    RunConfig,
    ConfigError,
    setup_config_cli_args,
    setup_tclfmt_config_cli_args,
)
from tclint.violations import Rule

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_example_config():
    config_path = MY_DIR / "data" / "tclint.toml"
    config = get_config(config_path, pathlib.Path.cwd())

    global_ = config.get_for_path(pathlib.Path())

    assert global_.exclude == ["ignore_me/", "ignore*.tcl", "/ignore_from_here"]
    assert global_.ignore == [Rule("unbraced-expr")]
    assert global_.extensions == ["tcl"]
    assert global_.commands == pathlib.Path("~/.tclint/openroad.json")

    assert global_.style_indent == 2
    assert global_.style_line_length == 80
    assert global_.style_indent_namespace_eval is False
    assert global_.style_spaces_in_braces is True

    group1 = config.get_for_path(pathlib.Path("other_file_group1/file.tcl"))
    assert group1.style_indent == 3
    assert group1.ignore == [Rule("command-args")]
    assert group1.style_line_length == 80

    group2 = config.get_for_path(pathlib.Path("other_file_group2/foo/file.tcl"))
    assert group2.style_indent == 2
    assert group2.style_spaces_in_braces is False


def test_invalid_rule():
    with pytest.raises(ConfigError) as excinfo:
        RunConfig.from_dict({"ignore": ["asdf"]}, pathlib.Path.cwd())

    if excinfo is not None:
        print(str(excinfo.value))


def test_pyproject():
    config = RunConfig.from_pyproject(MY_DIR / "data")
    global_ = config.get_for_path(pathlib.Path())
    assert global_.style_indent == 2
    assert global_.ignore == [Rule("unbraced-expr")]


def test_tclint_config_args():
    parser = argparse.ArgumentParser("tclint")
    setup_config_cli_args(parser)

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
    assert args.exclude == ["my_dir", "my_file"]
    assert args.extend_exclude == ["extend_to_file"]
    assert args.extensions == ["sdc", "exp"]
    assert args.commands == pathlib.Path("commands.json")
    assert args.style_line_length == 79


def test_tclfmt_config_args():
    parser = argparse.ArgumentParser("tclfmt")
    setup_tclfmt_config_cli_args(parser)

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

    assert args.exclude == ["my_dir", "my_file"]
    assert args.extend_exclude == ["extend_to_file"]
    assert args.extensions == ["sdc", "exp"]
    assert args.commands == pathlib.Path("commands.json")
    assert args.style_indent == 5
    assert args.style_max_blank_lines == 4
    assert args.style_indent_namespace_eval is True
    assert args.style_spaces_in_braces is False


def test_invalid_tclint_args():
    parser = argparse.ArgumentParser("tclint", exit_on_error=False)
    setup_config_cli_args(parser)

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
    setup_tclfmt_config_cli_args(parser)

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
        {"fileset": [{"style": {"indent": 4}}]},  # missing key
        {"fileset": [{"paths": ["dir"], "style": {"indent": "not-a-number"}}]},
        {"extra-key": "value"},
    ]:
        with pytest.raises(ConfigError) as excinfo:
            RunConfig.from_dict(config, pathlib.Path.cwd())

        # For manually auditing error messages
        print(excinfo.value)
