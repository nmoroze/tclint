import pathlib

import pytest

from tclint.config import get_config, Config, ConfigError

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_example_config():
    config_path = MY_DIR / "data" / "tclint.toml"
    config = get_config(config_path)

    assert config.exclude == list(map(pathlib.Path, ["ignore_me/", "ignore.tcl"]))
    assert config.ignore == [
        "spacing",
        {"path": pathlib.Path("files_with_bad_indent/"), "rules": ["indent"]},
    ]

    assert config.style_indent == 2
    assert config.style_line_length == 100
    assert config.style_aligned_set is True


def test_invalid_rule():
    with pytest.raises(ConfigError):
        Config.from_dict({"ignore": ["asdf"]})


def test_pyproject():
    config = Config.from_pyproject(MY_DIR / "data")
    assert config.style_indent == 2
    assert config.ignore == ["spacing"]
