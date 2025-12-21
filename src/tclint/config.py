import argparse
import pathlib
from typing import Union, List, Callable
from typing import Optional as OptionalType, NamedTuple
import dataclasses
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from voluptuous import Schema, Optional, And, Coerce, Invalid, Range

from tclint.violations import Rule


class ExcludePattern(NamedTuple):
    """Exclude patterns are applied relative to a certain root. This dataclass is used
    to bundle the two."""

    pattern: str
    root: pathlib.Path


@dataclasses.dataclass
class Config:
    """This dataclass defines the supported Config fields and their default
    values. It provides an external interface for accessing config values.

    The type annotations defined here are fairly loose - more specific type
    validation (and normalization) is defined by `validators` below.
    """

    exclude: List[ExcludePattern] = dataclasses.field(default_factory=list)
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
        elif isinstance(self.style_indent, tuple):
            return " " * self.style_indent[0]

        # Should be unreachable, validated on ingestion of config
        raise ValueError(
            f"unexpected value for config.style_indent: {self.style_indent}"
        )

    def get_indent_mixed_tab_size(self) -> int:
        if isinstance(self.style_indent, tuple):
            return self.style_indent[1]
        return 0

    def diff(self) -> str:
        """Return string representation of Config only showing fields that differ from
        default instance."""
        default_config = Config()
        values = []
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            default = getattr(default_config, field.name)
            if value != default:
                values.append(f"{field.name}={value}")
        return f"Config({', '.join(values)})"


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


def _add_root(root: pathlib.Path) -> Callable[[pathlib.Path], pathlib.Path]:
    """Resolve path relative to `root.`"""

    def _path(path: pathlib.Path) -> pathlib.Path:
        path = path.expanduser()
        if not path.is_absolute():
            path = root / path
        return path

    return _path


def parse_mixed(v: str) -> tuple[int, int]:
    """Parse --indent=mixed,<s>,<t>."""
    s = v.split(",")
    if not (len(s) == 3 and s[0] == "mixed" and s[1].isdigit() and s[2].isdigit()):
        raise ValueError()
    return (int(s[1]), int(s[2]))


# Define validators as module variables so they can be reused for config file schema
# validation and CLI argument parsing.


def _validate_exclude(root):
    """Along with parsing the list, bundles exclude patterns with their root."""
    return And(_str2list, [lambda p: ExcludePattern(p, root)])


_validate_ignore = And(
    _str2list,
    [
        Coerce(Rule, msg="invalid rule ID"),
    ],
)


def _validate_commands(root):
    return And(Coerce(pathlib.Path), _add_root(root))


_validate_extensions = _str2list
_validate_style_indent = Coerce(
    lambda v: (
        v
        if v == "tab"
        else (
            int(v)
            if isinstance(v, int) or (isinstance(v, str) and v.isdigit())
            else parse_mixed(v)
        )
    ),
    msg="expected integer, 'tab', or 'mixed',integer,integer",
)
_validate_style_line_length = Coerce(int)
_validate_style_max_blank_lines = And(
    Coerce(int),
    Range(min=1),
)
_validate_style_indent_namespace_eval = bool
_validate_style_spaces_in_braces = bool


def _error_if_dynamic_plugin(p: pathlib.Path):
    if p.suffix == ".py":
        raise Invalid(
            "dynamic plugins cannot be specified via config file for security"
            " reasons. Use --commands instead."
        )
    return p


def _validate_config(config: dict, root: pathlib.Path):
    """Validates dictionary read from TOML config file. Individual value validators
    are implemented in the module-level variables above; this defines the actual
    structure of the schema.

    root is used to resolve values that may be relative to a certain path.
    """
    base_config = {
        Optional("ignore"): _validate_ignore,
        # tclint rejects paths to dynamic plugins in the config file. This restriction
        # is designed to make it explicit when tclint is executing external code.
        Optional("commands"): And(_validate_commands(root), _error_if_dynamic_plugin),
        Optional("style"): {
            Optional("indent"): _validate_style_indent,
            Optional("line-length"): _validate_style_line_length,
            Optional("max-blank-lines"): _validate_style_max_blank_lines,
            Optional("indent-namespace-eval"): _validate_style_indent_namespace_eval,
            Optional("spaces-in-braces"): _validate_style_spaces_in_braces,
        },
    }

    schema = Schema({
        # exclude and extensions can only be used in global context
        Optional("exclude"): _validate_exclude(root),
        Optional("extensions"): _validate_extensions,
        **base_config,
    })

    try:
        return schema(config)
    except Invalid as e:
        if not e.path:
            raise ConfigError(e.error_message)

        # Stringify error path to my own taste.
        path: List[str] = []
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


def _argparsify(validator: Callable) -> Callable:
    """Wrapper that applies a voluptuous-style validator and is compatible with
    argparse's type argument."""

    def func(s):
        try:
            return Schema(validator)(s)
        except Invalid as e:
            raise argparse.ArgumentTypeError(str(e))

    return func


def _add_bool(group, parser, dest, yes_flag, no_flag):
    mutex_group = group.add_mutually_exclusive_group(required=False)
    mutex_group.add_argument(yes_flag, dest=dest, action="store_true")
    mutex_group.add_argument(no_flag, dest=dest, action="store_false")
    parser.set_defaults(**{dest: None})


def setup_common_config_cli_args(config_group, cwd: pathlib.Path):
    """
    This method defines config-related CLI arguments common to both tclint and tclfmt.

    The destvars of these switches should match the fields of Config.

    Relative paths and exclude patterns will be resolved relative to `cwd`. It may seem
    weird to specify this in a "setup" function (as opposed to Config.apply_cli_args),
    but the paths are resolved by the validator functions configured here. For our use
    case, this is fine since the setup and application of the CLI args are close
    together in the application code.
    """
    config_group.add_argument(
        "--exclude",
        type=_argparsify(_validate_exclude(cwd)),
        metavar='"path1, path2, ..."',
    )
    config_group.add_argument(
        "--extend-exclude",
        type=_argparsify(_validate_exclude(cwd)),
        metavar='"path1, path2, ..."',
    )
    config_group.add_argument(
        "--extensions",
        type=_argparsify(_validate_extensions),
        metavar='"tcl, xdc, ..."',
    )
    config_group.add_argument(
        "--commands", type=_argparsify(_validate_commands(cwd)), metavar="<path>"
    )


def setup_config_cli_args(parser, cwd: pathlib.Path):
    """This method defines config-related CLI arguments used by tclint.

    The destvars of these switches should match the fields of Config.
    """
    config_group = parser.add_argument_group("configuration arguments")

    config_group.add_argument(
        "--ignore", type=_argparsify(_validate_ignore), metavar='"rule1, rule2, ..."'
    )
    config_group.add_argument(
        "--extend-ignore",
        type=_argparsify(_validate_ignore),
        metavar='"rule1, rule2, ..."',
    )
    setup_common_config_cli_args(config_group, cwd)
    config_group.add_argument(
        "--style-line-length",
        type=_argparsify(_validate_style_line_length),
        metavar="<line_length>",
    )


def setup_tclfmt_config_cli_args(parser, cwd: pathlib.Path):
    """This method defines the subset of config-related CLI arguments used by tclfmt.

    The destvars of these switches should match the fields of Config.
    """
    config_group = parser.add_argument_group("configuration arguments")

    setup_common_config_cli_args(config_group, cwd)

    config_group.add_argument(
        "--indent",
        type=_argparsify(_validate_style_indent),
        metavar="<indent>",
        dest="style_indent",
    )
    config_group.add_argument(
        "--max-blank-lines",
        type=_argparsify(_validate_style_max_blank_lines),
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
        config_dict = _validate_config(config_dict, root)
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

        if not path.exists() or path.is_dir():
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


def load_config_at(directory: pathlib.Path) -> OptionalType[Config]:
    for path in DEFAULT_CONFIGS:
        try:
            rc = RunConfig.from_path(directory / path, directory)
            return rc._global_config
        except FileNotFoundError:
            pass

    try:
        rc = RunConfig.from_pyproject(directory=directory)
        return rc._global_config
    except ConfigError as e:
        raise e
    except (FileNotFoundError, tomllib.TOMLDecodeError, KeyError):
        # just skip if file doesn't exist, contains TOML errors, or tclint key not found
        pass

    return None
