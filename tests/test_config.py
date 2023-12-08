import pathlib

import pytest

from tclint.config import get_config, RunConfig, ConfigError

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_example_config():
    config_path = MY_DIR / "data" / "tclint.toml"
    config = get_config(config_path)

    global_ = config.get_for_path(pathlib.Path())

    assert global_.exclude == list(map(pathlib.Path, ["ignore_me/", "ignore.tcl"]))
    assert global_.ignore == [
        "spacing",
        {"path": pathlib.Path("files_with_bad_indent/"), "rules": ["indent"]},
    ]

    assert global_.style_indent == 2
    assert global_.style_line_length == 100
    assert global_.style_allow_aligned_sets is True

    group1 = config.get_for_path(pathlib.Path("other_file_group1/file.tcl"))
    assert group1.style_indent == 3
    assert group1.ignore == ["command-args"]
    assert group1.style_line_length == 100

    group2 = config.get_for_path(pathlib.Path("other_file_group2/foo/file.tcl"))
    assert group2.style_indent == 2
    assert group2.style_allow_aligned_sets is False


def test_invalid_rule():
    with pytest.raises(ConfigError):
        RunConfig.from_dict({"ignore": ["asdf"]})


def test_pyproject():
    config = RunConfig.from_pyproject(MY_DIR / "data")
    global_ = config.get_for_path(pathlib.Path())
    assert global_.style_indent == 2
    assert global_.ignore == ["spacing"]
