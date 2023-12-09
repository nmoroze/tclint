import sys
from importlib.metadata import entry_points
from typing import List, Dict

from tclint.commands import builtin as _builtin

# import to expose in package
from tclint.commands.utils import CommandArgError

__all__ = ["CommandArgError", "validate_command_plugins", "get_commands"]


def _get_entry_points(group):
    if sys.version_info < (3, 10):
        eps = entry_points()
        try:
            return eps[group]
        except KeyError:
            return []
    else:
        return entry_points(group=group)


def validate_command_plugins(plugins: List[str]) -> List[str]:
    plugins = set(plugins)
    installed_plugins = _get_entry_points("tclint.plugins")

    plugins_found = set()
    for plugin in installed_plugins:
        if plugin.name not in plugins:
            continue

        try:
            module = plugin.load()
        except Exception:
            print(
                f"Warning: skipping plugin {plugin.name} due to an error in the plugin"
            )
            continue

        if not hasattr(module, "commands"):
            print(
                f"Warning: skipping plugin {plugin.name} since it does not define"
                " commands"
            )
            continue

        plugins_found.add(plugin.name)

    plugins_diff = plugins.difference(plugins_found)
    if plugins_diff:
        plugins_str = ", ".join(plugins_diff)
        print(f"Warning: following plugins could not be found: {plugins_str}")

    return list(plugins_found)


def get_commands(plugins: List[str] = None) -> Dict:
    plugins_to_find = set(plugins)
    installed_plugins = _get_entry_points("tclint.plugins")

    commands = {}
    commands.update(_builtin.commands)

    for plugin in installed_plugins:
        try:
            plugins_to_find.remove(plugin.name)
        except KeyError:
            continue

        module = plugin.load()
        plugin_commands = getattr(module, "commands")

        commands.update(plugin_commands)

    return commands
