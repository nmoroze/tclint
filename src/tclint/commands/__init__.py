from typing import List, Dict

from tclint.commands import builtin as _builtin
from tclint.commands.plugins import PluginManager

# import to expose in package
from tclint.commands.utils import CommandArgError

__all__ = ["CommandArgError", "validate_command_plugins", "get_commands"]


def validate_command_plugins(plugins: List[str]) -> List[str]:
    valid_plugins = []
    for plugin in set(plugins):
        if PluginManager.load(plugin) is not None:
            valid_plugins.append(plugin)

    return valid_plugins


def get_commands(plugins: List[str]) -> Dict:
    commands = {}
    commands.update(_builtin.commands)

    for plugin in set(plugins):
        plugin_commands = PluginManager.load(plugin)
        if plugin_commands is not None:
            commands.update(plugin_commands)

    return commands
