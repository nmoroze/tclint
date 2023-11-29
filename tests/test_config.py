import pathlib

from tclint.config import get_config

MY_DIR = pathlib.Path(__file__).parent.resolve()


def test_example_config():
    config_path = MY_DIR / "data" / "tclint.toml"
    config = get_config(config_path)

    assert config.exclude == list(map(pathlib.Path, ["ignore_me/", "ignore.tcl"]))
    assert config.ignore == ["spacing"]

    assert config.style_indent == 2
    assert config.style_line_length == 100
    assert config.style_aligned_set is True
