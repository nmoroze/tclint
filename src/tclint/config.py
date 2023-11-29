import pathlib

import toml
from schema import Schema, Optional, Or, Use, SchemaError


class Config:
    def __init__(
        self,
        ignore=None,
        exclude=None,
        style_indent=None,
        style_line_length=None,
        style_aligned_set=None,
    ):
        self.ignore = []
        if ignore is not None:
            self.ignore = ignore

        self.exclude = []
        if exclude is not None:
            self.exclude = exclude

        self.style_indent = 4
        if style_indent is not None:
            self.style_indent = style_indent

        self.style_line_length = 80
        if style_line_length is not None:
            self.style_line_length = style_line_length

        self.style_aligned_set = False
        if style_aligned_set is not None:
            self.style_aligned_set = style_aligned_set


class ConfigError(Exception):
    pass


def get_config(config_path=None) -> Config:
    DEFAULT_CONFIGS = ("tclint.toml", ".tclint")

    if config_path is None:
        for path in DEFAULT_CONFIGS:
            if pathlib.Path(path).exists():
                config_path = path
                break

    if config_path is None:
        return Config()

    with open(config_path, "r") as f:
        config_str = f.read()

    try:
        return config_from_str(config_str)
    except ConfigError as e:
        raise ConfigError(f"{config_path}: {e}")


def config_from_str(config_str) -> Config:
    schema = Schema({
        # note: it's ok if paths don't exist - allows for generic
        # configurations with directories like .git/ excluded
        Optional("exclude"): [Use(pathlib.Path)],
        # TODO: validate that it's a correct ID
        Optional("ignore"): [str],
        Optional("style"): {
            Optional("indent"): Or(
                lambda v: v == "tab", int, error="indent must be integer or 'tab'"
            ),
            Optional("line-length"): Use(int, error="line-length must be integer"),
            Optional("allow-aligned-sets"): Use(
                bool, error="allow-aligned-sets must be a bool"
            ),
        },
    })

    try:
        data = toml.loads(config_str)
    except toml.decoder.TomlDecodeError as e:
        raise ConfigError(str(e))

    try:
        config = schema.validate(data)
    except SchemaError as e:
        error_s = str(e).replace("\n", " ")
        raise ConfigError(error_s)

    style_config = config.get("style", {})

    return Config(
        exclude=config.get("exclude", None),
        ignore=config.get("ignore", None),
        style_indent=style_config.get("indent", None),
        style_line_length=style_config.get("line-length", None),
        style_aligned_set=style_config.get("allow-aligned-sets", None),
    )
