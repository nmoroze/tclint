from collections.abc import Sequence
import pathlib
from typing import List, Dict, Union

from tclint.commands import builtin as _builtin
from tclint.commands.plugins import PluginManager

# import to expose in package
from tclint.commands.checks import CommandArgError

__all__ = ["CommandArgError", "validate_command_plugins", "get_commands"]


def validate_command_plugins(plugins: List[str]) -> List[str]:
    valid_plugins = []
    for plugin in set(plugins):
        if PluginManager.load(plugin) is not None:
            valid_plugins.append(plugin)

    return valid_plugins


def get_commands(plugins: Sequence[Union[str, pathlib.Path]]) -> Dict:
    commands = {}
    commands.update(_builtin.commands)

    for plugin in plugins:
        if isinstance(plugin, str):
            plugin_commands = PluginManager.load(plugin)
        elif isinstance(plugin, pathlib.Path):
            if plugin.suffix == ".py":
                plugin_commands = PluginManager.load_from_py(plugin)
            else:
                plugin_commands = PluginManager.load_from_spec(plugin)
        else:
            raise TypeError(f"Plugins must be strings or paths, got {type(plugin)}")

        if plugin_commands is not None:
            commands.update(plugin_commands)

    return commands
