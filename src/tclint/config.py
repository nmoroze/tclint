import argparse
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
from tclint import utils


def _flatten(d, prefix=None):
    if prefix is None:
        prefix = []

    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flat.update(_flatten(v, prefix=prefix + [k]))
        else:
            flat["_".join(prefix + [k]).replace("-", "_")] = v

    return flat


# Constraint: all non-boolean validators need to be able to normalize a value
# from a string in order to normalize CLI args. This means one could put e.g. a
# string rep of a list into a .toml config file, but we shouldn't document this,
# since it won't be considered stable behavior.


def _str2list(s):
    """Parse comma-separated string to list."""
    if isinstance(s, str):
        if s == "":
            return []
        return [v.strip() for v in s.split(",")]
    return s


validators = {
    "exclude": And(Use(_str2list), [Use(pathlib.Path)]),
    "ignore": And(
        Use(_str2list),
        [
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
    ),
    "style_indent": Or(
        lambda v: v == "tab", Use(int), error="indent must be integer or 'tab'"
    ),
    "style_line_length": Use(int, error="line-length must be integer"),
    "style_allow_aligned_sets": Use(bool, error="allow-aligned-sets must be a bool"),
}


def _validate_config(config):
    schema = Schema({
        # note: it's ok if paths don't exist - allows for generic
        # configurations with directories like .git/ excluded
        Optional("exclude"): validators["exclude"],
        Optional("ignore"): validators["ignore"],
        Optional("style"): {
            Optional("indent"): validators["style_indent"],
            Optional("line-length"): validators["style_line_length"],
            Optional("allow-aligned-sets"): validators["style_allow_aligned_sets"],
        },
    })

    try:
        return schema.validate(config)
    except SchemaError as e:
        error_s = str(e).replace("\n", " ")
        raise ConfigError(error_s)


@dataclass
class Config:
    ignore: List[pathlib.Path]
    exclude: List[Union[dict, str]]
    style_indent: Union[str, int]
    style_line_length: int
    style_allow_aligned_sets: bool

    def __init__(
        self,
        ignore=None,
        exclude=None,
        style_indent=None,
        style_line_length=None,
        style_allow_aligned_sets=None,
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

        self.style_allow_aligned_sets = False
        if style_allow_aligned_sets is not None:
            self.style_allow_aligned_sets = style_allow_aligned_sets

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
        if args.style_allow_aligned_sets is not None:
            self.style_allow_aligned_sets = args.style_allow_aligned_sets


class RunConfig:
    def __init__(self, global_config=None, fileset_configs=None):
        if global_config is not None:
            self._global_config = global_config
        else:
            self._global_config = Config()

        self._fileset_configs = {}
        if fileset_configs is not None:
            self._fileset_configs = fileset_configs

    def get_for_path(self, path) -> Config:
        path = path.resolve()
        for fileset_paths, config in self._fileset_configs.items():
            for fileset_path in fileset_paths:
                if utils.is_relative_to(path, fileset_path):
                    return config

        return self._global_config

    @property
    def exclude(self):
        return self._global_config.exclude

    @classmethod
    def from_dict(cls, config_dict: dict):
        global_config_dict = config_dict.copy()
        try:
            global_config_dict.pop("fileset")
        except KeyError:
            pass
        global_config_dict = _validate_config(global_config_dict)
        global_config_dict = _flatten(global_config_dict)
        global_config = Config(**global_config_dict)

        fileset_configs = {}
        if "fileset" in config_dict:
            for config in config_dict["fileset"]:
                try:
                    paths = config["paths"]
                except KeyError:
                    raise ConfigError("'fileset' table requires 'paths' entry")

                paths = tuple([pathlib.Path(path).resolve() for path in paths])
                fileset_config_d = config.copy()
                fileset_config_d.pop("paths")
                fileset_config_d = _validate_config(fileset_config_d)
                fileset_config_d = _flatten(fileset_config_d)

                # pull in default values from global config
                full_fileset_config = global_config_dict.copy()
                full_fileset_config.update(fileset_config_d)

                fileset_configs[paths] = Config(**full_fileset_config)

        return cls(global_config, fileset_configs)

    def apply_args(self, args):
        self._global_config.apply_args(args)
        for fileset_config in self._fileset_configs.values():
            fileset_config.apply_args(args)

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


class ConfigError(Exception):
    pass


def _get_base_config(config_path) -> RunConfig:
    DEFAULT_CONFIGS = ("tclint.toml", ".tclint")

    # user-supplied
    if config_path is not None:
        try:
            return RunConfig.from_path(config_path)
        except FileNotFoundError:
            raise ConfigError(f"path {config_path} doesn't exist")

    for path in DEFAULT_CONFIGS:
        try:
            return RunConfig.from_path(path)
        except FileNotFoundError:
            pass

    try:
        return RunConfig.from_pyproject()
    except ConfigError as e:
        raise e
    except (FileNotFoundError, tomllib.TOMLDecodeError, KeyError):
        # just skip if file doesn't exist, contains TOML errors, or tclint key not found
        pass

    return RunConfig()


def get_config(args) -> RunConfig:
    config = _get_base_config(args.config)
    config.apply_args(args)

    return config


def add_switches(parser):
    def validator(key):
        def func(s):
            try:
                return Schema(validators[key]).validate(s)
            except SchemaError as e:
                error_s = str(e).replace("\n", " ")
                raise argparse.ArgumentTypeError(error_s)

        return func

    config_group = parser.add_argument_group("Override configuration")

    config_group.add_argument("--ignore", type=validator("ignore"))
    config_group.add_argument("--extend-ignore", type=validator("ignore"))
    config_group.add_argument("--exclude", type=validator("exclude"))
    config_group.add_argument("--extend-exclude", type=validator("exclude"))
    config_group.add_argument("--style-indent", type=validator("style_indent"))
    config_group.add_argument(
        "--style-line-length", type=validator("style_line_length")
    )

    aligned_sets_parser = config_group.add_mutually_exclusive_group(required=False)
    aligned_sets_parser.add_argument(
        "--style-aligned-sets", dest="style_allow_aligned_sets", action="store_true"
    )
    aligned_sets_parser.add_argument(
        "--style-no-aligned-sets", dest="style_allow_aligned_sets", action="store_false"
    )
    parser.set_defaults(style_allow_aligned_sets=None)
