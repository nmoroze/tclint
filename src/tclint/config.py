import pathlib
from typing import Union, List
from dataclasses import dataclass

try:
    import tomllib
except ModuleNotFoundError:
    # tomli backfills on Python < 3.11
    import tomli as tomllib

from schema import Schema, Optional, Or, Use, SchemaError, And

from tclint.violations import violation_types


@dataclass
class Config:
    ignore: List[pathlib.Path]
    exclude: List[Union[dict, str]]
    style_indent: Union[str, int]
    style_line_length: int
    style_aligned_set: bool

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
            Optional("ignore"): [
                Or(
                    And(
                        str,
                        lambda s: s in violation_types,
                        error="invalid rule ID provided for 'ignore'",
                    ),
                    {
                        "path": Use(pathlib.Path),
                        "rules": [
                            And(
                                str,
                                lambda s: s in violation_types,
                                error="invalid rule ID provided for 'ignore'",
                            )
                        ],
                    },
                )
            ],
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

        with open(path, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"{path}: {e}")

        try:
            return cls.from_dict(data)
        except ConfigError as e:
            raise ConfigError(f"{path}: {e}")

    @classmethod
    def from_pyproject(cls, directory=None):
        if directory is None:
            directory = pathlib.Path(".")
        else:
            directory = pathlib.Path(directory)

        path = directory / "pyproject.toml"

        if not path.exists():
            raise FileNotFoundError

        with open(path, "rb") as f:
            data = tomllib.load(f)

        tclint_config = data.get("tool", {})["tclint"]

        try:
            return cls.from_dict(tclint_config)
        except ConfigError as e:
            raise ConfigError(f"pyproject.toml: {e}")

    def apply_args(self, args):
        if args.ignore is not None:
            self.ignore = args.ignore
        if args.extend_ignore is not None:
            self.ignore.extend(args.extend_ignore)
        if args.exclude is not None:
            self.exclude = args.exclude
        if args.extend_exclude is not None:
            self.exclude.extend(args.extend_exclude)
        if args.style_indent is not None:
            self.style_indent = args.style_indent
        if args.style_line_length is not None:
            self.style_line_length = args.style_line_length
        if args.style_aligned_sets is not None:
            self.style_aligned_set = args.style_aligned_sets


class ConfigError(Exception):
    pass


def _get_base_config(config_path) -> Config:
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


def get_config(args) -> Config:
    config = _get_base_config(args.config)
    config.apply_args(args)

    return config


def add_switches(parser):
    def str2list(s, cast=lambda x: x):
        """Parse comma-separated string to list."""
        return [cast(v.strip()) for v in s.split(",")]

    config_group = parser.add_argument_group("Override configuration")

    config_group.add_argument("--ignore", type=str2list)
    config_group.add_argument("--extend-ignore", type=str2list)
    config_group.add_argument(
        "--exclude", type=lambda s: str2list(s, cast=pathlib.Path)
    )
    config_group.add_argument(
        "--extend-exclude", type=lambda s: str2list(s, cast=pathlib.Path)
    )
    config_group.add_argument(
        "--style-indent", type=lambda s: s if s == "tab" else int(s)
    )
    config_group.add_argument("--style-line-length", type=int)

    aligned_sets_parser = config_group.add_mutually_exclusive_group(required=False)
    aligned_sets_parser.add_argument(
        "--style-aligned-sets", dest="style_aligned_sets", action="store_true"
    )
    aligned_sets_parser.add_argument(
        "--style-no-aligned-sets", dest="style_aligned_sets", action="store_false"
    )
