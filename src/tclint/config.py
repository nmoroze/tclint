import argparse
import pathlib
from typing import Union, List, Any
from typing import Optional as OptionalType
import dataclasses
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from schema import Schema, Optional, Or, Use, SchemaError, And

from tclint.violations import Rule
from tclint import utils


@dataclasses.dataclass
class Config:
    """This dataclass defines the supported Config fields and their default
    values. It provides an external interface for accessing config values.

    The type annotations defined here are fairly loose - more specific type
    validation (and normalization) is defined by `validators` below.
    """

    exclude: List[Any] = dataclasses.field(default_factory=list)
    ignore: List[Any] = dataclasses.field(default_factory=list)
    commands: OptionalType[pathlib.Path] = dataclasses.field(default=None)
    extensions: List[str] = dataclasses.field(
        default_factory=lambda: ["tcl", "sdc", "xdc", "upf"]
    )
    style_indent: Union[str, int] = dataclasses.field(default=4)
    style_line_length: int = dataclasses.field(default=80)
    style_allow_aligned_sets: bool = dataclasses.field(default=False)
    style_max_blank_lines: int = dataclasses.field(default=2)
    style_indent_namespace_eval: bool = dataclasses.field(default=True)
    style_spaces_in_braces: bool = dataclasses.field(default=False)

    def apply_cli_args(self, args):
        args_dict = vars(args)
        for field in dataclasses.fields(self):
            if field.name in args_dict and args_dict[field.name] is not None:
                setattr(self, field.name, args_dict[field.name])

        # Special arguments that aren't handled automatically
        if args.extend_exclude is not None:
            self.exclude.extend(args.extend_exclude)

        if args.extend_ignore is not None:
            self.ignore.extend(args.extend_ignore)


# Validators using `schema` library that check and normalize config inputs.
# Used for checking both config files as well as config-related CLI args.

# Using these for CLI args adds a constraint that all non-boolean validators
# need to be able to normalize a value from a string. This means one could put
# e.g. a string representation of a list into a .toml config file, but we shouldn't
# document this, since it won't be considered stable behavior.

# _str2list handles this string-to-list normalization.


def _str2list(s):
    if isinstance(s, str):
        if s == "":
            return []
        return [v.strip() for v in s.split(",")]
    return s


_VALIDATORS = {
    # note: it's ok if paths don't exist - allows for generic
    # configurations with directories like .git/ excluded
    "exclude": Use(_str2list),
    "ignore": And(
        Use(_str2list),
        [
            Or(
                Use(
                    Rule,
                    error="invalid rule ID provided for 'ignore'",
                ),
                {
                    "path": Use(pathlib.Path),
                    "rules": [
                        Use(
                            Rule,
                            error="invalid rule ID provided for 'ignore'",
                        )
                    ],
                },
            )
        ],
    ),
    "commands": Use(pathlib.Path),
    "extensions": Use(_str2list),
    "style_indent": Or(
        lambda v: v == "tab", Use(int), error="indent must be integer or 'tab'"
    ),
    "style_line_length": Use(int, error="line-length must be integer"),
    "style_allow_aligned_sets": Use(bool, error="allow-aligned-sets must be a bool"),
    "style_max_blank_lines": And(
        Use(int),
        # we could technically support i >= 0, but I think 0 would be a weird
        # setting and this lets us ignore pluralizing the violation message :)
        lambda i: i >= 1,
        error="max-blank-lines must be an integer with value at least 1",
    ),
    "style_indent_namespace_eval": Use(
        bool, error="indent-namespace-eval must be a bool"
    ),
    "style_spaces_in_braces": Use(bool, error="spaces-in-braces must be a bool"),
}


def _validate_config(config):
    """Validates dictionary read from TOML config file. Individual value validators
    are implemented in the global dict, this defines the actual structure of the
    schema."""

    base_config = {
        Optional("ignore"): _VALIDATORS["ignore"],
        Optional("commands"): _VALIDATORS["commands"],
        Optional("style"): {
            Optional("indent"): _VALIDATORS["style_indent"],
            Optional("line-length"): _VALIDATORS["style_line_length"],
            Optional("allow-aligned-sets"): _VALIDATORS["style_allow_aligned_sets"],
            Optional("max-blank-lines"): _VALIDATORS["style_max_blank_lines"],
            Optional("indent-namespace-eval"): _VALIDATORS[
                "style_indent_namespace_eval"
            ],
            Optional("spaces-in-braces"): _VALIDATORS["style_spaces_in_braces"],
        },
    }

    schema = Schema({
        # exclude and extensions can only be used in global context
        Optional("exclude"): _VALIDATORS["exclude"],
        Optional("extensions"): _VALIDATORS["extensions"],
        **base_config,
        Optional("fileset"): Schema([{"paths": [Use(pathlib.Path)], **base_config}]),
    })

    try:
        return schema.validate(config)
    except SchemaError as e:
        if e.errors[-1] is not None:
            error = e.errors[-1]
        else:
            error = e.autos[-1]
        raise ConfigError(error)


def setup_config_cli_args(parser):
    """This method defines config-related CLI arguments.

    The destvars of these switches should match the fields of Config.
    """
    config_group = parser.add_argument_group("configuration arguments")

    def validator(key):
        def func(s):
            try:
                return Schema(_VALIDATORS[key]).validate(s)
            except SchemaError as e:
                error_s = str(e).replace("\n", " ")
                raise argparse.ArgumentTypeError(error_s)

        return func

    def add_bool(dest, yes_flag, no_flag):
        mutex_group = config_group.add_mutually_exclusive_group(required=False)
        mutex_group.add_argument(yes_flag, dest=dest, action="store_true")
        mutex_group.add_argument(no_flag, dest=dest, action="store_false")
        parser.set_defaults(**{dest: None})

    config_group.add_argument(
        "--ignore", type=validator("ignore"), metavar='"rule1, rule2, ..."'
    )
    config_group.add_argument(
        "--extend-ignore", type=validator("ignore"), metavar='"rule1, rule2, ..."'
    )
    config_group.add_argument(
        "--exclude", type=validator("exclude"), metavar='"path1, path2, ..."'
    )
    config_group.add_argument(
        "--extend-exclude", type=validator("exclude"), metavar='"path1, path2, ..."'
    )
    config_group.add_argument(
        "--extensions", type=validator("extensions"), metavar='"tcl, xdc, ..."'
    )
    config_group.add_argument(
        "--commands", type=validator("commands"), metavar="<path>"
    )
    config_group.add_argument(
        "--style-indent", type=validator("style_indent"), metavar="<indent>"
    )
    config_group.add_argument(
        "--style-line-length",
        type=validator("style_line_length"),
        metavar="<line_length>",
    )
    config_group.add_argument(
        "--style-max-blank-lines",
        type=validator("style_max_blank_lines"),
        metavar="<max_blank_lines>",
    )

    add_bool(
        "style_allow_aligned_sets",
        "--style-aligned-sets",
        "--style-no-aligned-sets",
    )
    add_bool(
        "style_indent_namespace_eval",
        "--style-indent-namespace-eval",
        "--style-no-indent-namespace-eval",
    )
    add_bool(
        "style_spaces_in_braces",
        "--style-spaces-in-braces",
        "--style-no-spaces-in-braces",
    )


def _flatten(d, prefix=None):
    """Flattens TOML config dictionary structure to match the flat set of fields
    expected by Config dataclass."""
    if prefix is None:
        prefix = []

    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            flat.update(_flatten(v, prefix=prefix + [k]))
        else:
            flat["_".join(prefix + [k]).replace("-", "_")] = v

    return flat


class RunConfig:
    """Class that holds information about both global and fileset configs. User
    code can get a Config object that applies to a particular file by calling
    get_from_path() and supplying that file's path."""

    def __init__(self, global_config=None, fileset_configs=None):
        if global_config is not None:
            self._global_config = global_config
        else:
            self._global_config = Config()

        self._fileset_configs = [
            # ([pathlib.Path...], Config])
        ]
        if fileset_configs is not None:
            self._fileset_configs = fileset_configs

    @property
    def exclude(self):
        return self._global_config.exclude

    @property
    def extensions(self):
        return self._global_config.extensions

    @classmethod
    def from_dict(cls, config_dict: dict):
        config_dict = _validate_config(config_dict)
        try:
            fileset_config_dicts = config_dict.pop("fileset")
        except KeyError:
            fileset_config_dicts = []

        config_dict = _flatten(config_dict)
        global_config = Config(**config_dict)

        fileset_configs = []
        for fileset_config in fileset_config_dicts:
            paths = fileset_config.pop("paths")

            paths = tuple([path.resolve() for path in paths])
            fileset_config = _flatten(fileset_config)

            # pull in default values from global config
            full_fileset_config = config_dict.copy()
            full_fileset_config.update(fileset_config)

            fileset_configs.append((paths, Config(**full_fileset_config)))

        return cls(global_config, fileset_configs)

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

    def get_for_path(self, path) -> Config:
        if path is None:
            return self._global_config

        path = path.resolve()
        for fileset_paths, config in self._fileset_configs:
            for fileset_path in fileset_paths:
                if utils.is_relative_to(path, fileset_path):
                    return config

        return self._global_config

    def apply_cli_args(self, args):
        self._global_config.apply_cli_args(args)
        for _, fileset_config in self._fileset_configs:
            fileset_config.apply_cli_args(args)


class ConfigError(Exception):
    pass


def get_config(config_path) -> RunConfig:
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
