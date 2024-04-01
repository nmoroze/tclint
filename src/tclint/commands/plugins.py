import sys
from importlib.metadata import entry_points
from typing import Dict, Optional


def _get_entry_points(group):
    if sys.version_info < (3, 10):
        eps = entry_points()
        try:
            return eps[group]
        except KeyError:
            return []
    else:
        return entry_points(group=group)


class _PluginManager:
    def __init__(self):
        self._loaded = {}
        self._installed = {}
        for plugin in _get_entry_points("tclint.plugins"):
            if plugin.name in self._installed:
                self._installed[plugin.name].append(plugin)
            else:
                self._installed[plugin.name] = [plugin]

    def load(self, name: str) -> Optional[Dict]:
        if name in self._loaded:
            return self._loaded[name]

        mod = self._load(name)
        self._loaded[name] = mod
        return mod

    def _load(self, name: str):
        if name not in self._installed:
            print(f"Warning: plugin {name} could not be found")
            return None

        installed = self._installed[name]
        if len(installed) > 1:
            print(f"Warning: found duplicate definitions for plugin {name}")

        for plugin in installed:
            try:
                module = plugin.load()
            except Exception as e:
                print(
                    f"Warning: skipping plugin {plugin.name} due to an error in the"
                    f" plugin: {e}"
                )
                continue

            if not hasattr(module, "commands"):
                print(
                    f"Warning: skipping plugin {plugin.name} since it does not define"
                    " commands"
                )
                continue

            return getattr(module, "commands")

        return None


# TODO: we'll probably want to construct this in the tclint entry point and pass
# it around rather than using a singleton instance, but this made for an easier
# refactor.
PluginManager = _PluginManager()
