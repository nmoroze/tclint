import pathlib
from typing import Union

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

    @classmethod
    def from_dict(cls, config_dict: dict):
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
            config = schema.validate(config_dict)
        except SchemaError as e:
            error_s = str(e).replace("\n", " ")
            raise ConfigError(error_s)

        style_config = config.get("style", {})

        return cls(
            exclude=config.get("exclude", None),
            ignore=config.get("ignore", None),
            style_indent=style_config.get("indent", None),
            style_line_length=style_config.get("line-length", None),
            style_aligned_set=style_config.get("allow-aligned-sets", None),
        )

    @classmethod
    def from_path(cls, path: Union[str, pathlib.Path]):
        path = pathlib.Path(path)

        if not path.exists():
            raise FileNotFoundError

        with open(path, "r") as f:
            try:
                data = toml.load(f)
            except toml.decoder.TomlDecodeError as e:
                raise ConfigError(f"{path}: {e}")

        try:
            return cls.from_dict(data)
        except ConfigError as e:
            raise ConfigError(f"{path}: {e}")

    @classmethod
    def from_pyproject(cls):
        path = pathlib.Path("pyproject.toml")

        if not path.exists():
            raise FileNotFoundError

        with open("pyproject.toml", "r") as f:
            data = toml.load(f)

        tclint_config = data.get("tool", {})["tclint"]

        try:
            return cls.from_dict(tclint_config)
        except ConfigError as e:
            raise ConfigError(f"pyproject.toml: {e}")


class ConfigError(Exception):
    pass


def get_config(config_path=None) -> Config:
    DEFAULT_CONFIGS = ("tclint.toml", ".tclint")

    # user-supplied
    if config_path is not None:
        try:
            return Config.from_path(config_path)
        except FileNotFoundError:
            raise ConfigError(f"path {config_path} doesn't exist")

    for path in DEFAULT_CONFIGS:
        try:
            return Config.from_path(path)
        except FileNotFoundError:
            pass

    try:
        return Config.from_pyproject()
    except ConfigError as e:
        raise e
    except Exception:
        pass

    return Config()
