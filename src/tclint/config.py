import argparse
import pathlib
from typing import Union, List
from typing import Optional as OptionalType
import dataclasses
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from voluptuous import Schema, Optional, And, Coerce, Invalid, Range

from tclint.violations import Rule


@dataclasses.dataclass
class Config:
    """This dataclass defines the supported Config fields and their default
    values. It provides an external interface for accessing config values.

    The type annotations defined here are fairly loose - more specific type
    validation (and normalization) is defined by `validators` below.
    """

    exclude: List[str] = dataclasses.field(default_factory=list)
    ignore: List[Rule] = dataclasses.field(default_factory=list)
    commands: OptionalType[pathlib.Path] = dataclasses.field(default=None)
    extensions: List[str] = dataclasses.field(
        default_factory=lambda: ["tcl", "sdc", "xdc", "upf"]
    )
    style_indent: OptionalType[Union[str, int]] = dataclasses.field(default=None)
    style_line_length: int = dataclasses.field(default=100)
    style_max_blank_lines: int = dataclasses.field(default=2)
    style_indent_namespace_eval: bool = dataclasses.field(default=True)
    style_spaces_in_braces: bool = dataclasses.field(default=False)

    def apply_cli_args(self, args):
        args_dict = vars(args)
        for field in dataclasses.fields(self):
            if field.name in args_dict and args_dict[field.name] is not None:
                setattr(self, field.name, args_dict[field.name])

        # Special arguments that aren't handled automatically
        if "extend_exclude" in args_dict and args_dict["extend_exclude"] is not None:
            self.exclude.extend(args_dict["extend_exclude"])

        if "extend_ignore" in args_dict and args_dict["extend_ignore"] is not None:
            self.ignore.extend(args_dict["extend_ignore"])

    def get_indent(self) -> str:
        """Get indent setting as string.

        This helper does two things. One, it's a helpful utility to factor out the logic
        required for calculating the indent. Two, it lets us ergonomically store if the
        indentation is not set in style_indent, which the LSP relies on.
        """
        if self.style_indent is None:
            # Default indent
            return " " * 4
        elif self.style_indent == "tab":
            return "\t"
        elif isinstance(self.style_indent, int):
            return " " * self.style_indent

        # Should be unreachable, validated on ingestion of config
        raise ValueError(
            f"unexpected value for config.style_indent: {self.style_indent}"
        )


# Validators using `voluptuous` library that check and normalize config inputs.
# Used for checking both config files as well as config-related CLI args.

# Using these for CLI args adds a constraint that all non-boolean validators
# need to be able to normalize a value from a string. This means one could put
# e.g. a string representation of a list into a .toml config file, but we shouldn't
# document this, since it won't be considered stable behavior.


def _str2list(s):
    """Handles string-to-list normalization."""
    if isinstance(s, str):
        if s == "":
            return []
        return [v.strip() for v in s.split(",")]
    return s


_VALIDATORS = {
    # note: it's ok if paths don't exist - allows for generic
    # configurations with directories like .git/ excluded
    "exclude": _str2list,
    "ignore": And(
        _str2list,
        [
            Coerce(Rule, msg="invalid rule ID"),
        ],
    ),
    "commands": Coerce(pathlib.Path),
    "extensions": _str2list,
    "style_indent": Coerce(
        lambda v: v if v == "tab" else int(v), msg="expected integer or 'tab'"
    ),
    "style_line_length": Coerce(int),
    "style_max_blank_lines": And(
        Coerce(int),
        # we could technically support i >= 0, but I think 0 would be a weird
        # setting and this lets us ignore pluralizing the violation message :)
        Range(min=1),
    ),
    "style_indent_namespace_eval": bool,
    "style_spaces_in_braces": bool,
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
        Optional("fileset"): Schema(
            [{"paths": [Coerce(pathlib.Path)], **base_config}], required=True
        ),
    })

    try:
        return schema(config)
    except Invalid as e:
        if not e.path:
            raise ConfigError(e.error_message)

        # Stringify error path to my own taste.
        path = []
        for item in e.path:
            if isinstance(item, int):
                # Brackets around indices
                if len(path) > 0:
                    path[-1] += f"[{item}]"
                else:
                    path.append(f"[{item}]")
            else:
                path.append(str(item))

        raise ConfigError(f"{e.error_message} ({'.'.join(path)})")


def _validator(key):
    def func(s):
        try:
            return Schema(_VALIDATORS[key])(s)
        except Invalid as e:
            raise argparse.ArgumentTypeError(str(e))

    return func


def _add_bool(group, parser, dest, yes_flag, no_flag):
    mutex_group = group.add_mutually_exclusive_group(required=False)
    mutex_group.add_argument(yes_flag, dest=dest, action="store_true")
    mutex_group.add_argument(no_flag, dest=dest, action="store_false")
    parser.set_defaults(**{dest: None})


def setup_common_config_cli_args(config_group):
    config_group.add_argument(
        "--exclude", type=_validator("exclude"), metavar='"path1, path2, ..."'
    )
    config_group.add_argument(
        "--extend-exclude", type=_validator("exclude"), metavar='"path1, path2, ..."'
    )
    config_group.add_argument(
        "--extensions", type=_validator("extensions"), metavar='"tcl, xdc, ..."'
    )
    config_group.add_argument(
        "--commands", type=_validator("commands"), metavar="<path>"
    )


def setup_config_cli_args(parser):
    """This method defines config-related CLI arguments.

    The destvars of these switches should match the fields of Config.
    """
    config_group = parser.add_argument_group("configuration arguments")

    config_group.add_argument(
        "--ignore", type=_validator("ignore"), metavar='"rule1, rule2, ..."'
    )
    config_group.add_argument(
        "--extend-ignore", type=_validator("ignore"), metavar='"rule1, rule2, ..."'
    )
    setup_common_config_cli_args(config_group)
    config_group.add_argument(
        "--style-line-length",
        type=_validator("style_line_length"),
        metavar="<line_length>",
    )


def setup_tclfmt_config_cli_args(parser):
    """This method defines the subset of config-related CLI arguments used by tclfmt.

    The destvars of these switches should match the fields of Config.
    """
    config_group = parser.add_argument_group("configuration arguments")

    setup_common_config_cli_args(config_group)

    config_group.add_argument(
        "--indent",
        type=_validator("style_indent"),
        metavar="<indent>",
        dest="style_indent",
    )
    config_group.add_argument(
        "--max-blank-lines",
        type=_validator("style_max_blank_lines"),
        metavar="<max_blank_lines>",
        dest="style_max_blank_lines",
    )
    _add_bool(
        config_group,
        parser,
        "style_indent_namespace_eval",
        "--indent-namespace-eval",
        "--no-indent-namespace-eval",
    )
    _add_bool(
        config_group,
        parser,
        "style_spaces_in_braces",
        "--spaces-in-braces",
        "--no-spaces-in-braces",
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
    def from_dict(cls, config_dict: dict, root: pathlib.Path):
        config_dict = _validate_config(config_dict)
        try:
            fileset_config_dicts = config_dict.pop("fileset")
        except KeyError:
            fileset_config_dicts = []

        config_dict = _flatten(config_dict)
        global_config = Config(**config_dict)

        fileset_configs = []
        for fileset_config in fileset_config_dicts:
            paths = []
            for path in fileset_config.pop("paths"):
                if not path.is_absolute():
                    path = root / path
                paths.append(path.resolve())

            fileset_config = _flatten(fileset_config)

            # pull in default values from global config
            full_fileset_config = config_dict.copy()
            full_fileset_config.update(fileset_config)

            fileset_configs.append((paths, Config(**full_fileset_config)))

        return cls(global_config, fileset_configs)

    @classmethod
    def from_path(cls, path: Union[str, pathlib.Path], root: pathlib.Path):
        path = pathlib.Path(path)

        if not path.exists():
            raise FileNotFoundError

        with open(path, "rb") as f:
            try:
                data = tomllib.load(f)
            except tomllib.TOMLDecodeError as e:
                raise ConfigError(f"{path}: {e}")

        try:
            return cls.from_dict(data, root)
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
            return cls.from_dict(tclint_config, directory)
        except ConfigError as e:
            raise ConfigError(f"pyproject.toml: {e}")

    def get_for_path(self, path) -> Config:
        if path is None:
            return self._global_config

        path = path.resolve()
        for fileset_paths, config in self._fileset_configs:
            for fileset_path in fileset_paths:
                if path.is_relative_to(fileset_path):
                    return config

        return self._global_config

    def apply_cli_args(self, args):
        self._global_config.apply_cli_args(args)
        for _, fileset_config in self._fileset_configs:
            fileset_config.apply_cli_args(args)


class ConfigError(Exception):
    pass


DEFAULT_CONFIGS = ("tclint.toml", ".tclint")


def get_config(
    config_path: OptionalType[pathlib.Path], root: pathlib.Path
) -> OptionalType[RunConfig]:
    """Loads a config file.

    If `config_path` is supplied, attempts to read config file from this path. If the
    path can't be found, raises a ConfigError.

    Otherwise, attempts to read config from `root`/{tclint.toml, .tclint,
    pyproject.toml} (in that order). If none of these files can be found, returns None.

    `root` is also used to resolve some relative paths in the config file.
    """
    # user-supplied
    if config_path is not None:
        try:
            return RunConfig.from_path(config_path, root)
        except FileNotFoundError:
            raise ConfigError(f"path {config_path} doesn't exist")

    for path in DEFAULT_CONFIGS:
        try:
            return RunConfig.from_path(root / path, root)
        except FileNotFoundError:
            pass

    try:
        return RunConfig.from_pyproject(directory=root)
    except ConfigError as e:
        raise e
    except (FileNotFoundError, tomllib.TOMLDecodeError, KeyError):
        # just skip if file doesn't exist, contains TOML errors, or tclint key not found
        pass

    return None
