from importlib_metadata import entry_points
import json
import pathlib
from typing import Dict, Optional
from types import ModuleType

import voluptuous

from tclint.commands.schema import schema as command_schema


class _PluginManager:
    def __init__(self):
        self._loaded = {}
        self._installed = {}
        self._loaded_specs = {}
        for plugin in entry_points(group="tclint.plugins"):
            if plugin.name in self._installed:
                print(f"Warning: found duplicate definitions for plugin {plugin.name}")
            self._installed[plugin.name] = plugin

    def load(self, name: str) -> Optional[Dict]:
        if name in self._loaded:
            return self._loaded[name]

        mod = self._load(name)
        self._loaded[name] = mod
        return mod

    def load_from_spec(self, path: pathlib.Path) -> Optional[Dict]:
        if path in self._loaded_specs:
            return self._loaded_specs[path]

        spec = self._load_from_spec(path)
        self._loaded_specs[path] = spec
        return spec

    def _load_from_spec(self, path: pathlib.Path) -> Optional[Dict]:
        try:
            with open(path.expanduser(), "r") as f:
                spec = json.load(f)
        except (FileNotFoundError, RuntimeError):
            print(f"Warning: command spec {path} not found, skipping...")
            return None

        try:
            # Apply defaults and validate the spec.
            spec = command_schema(spec)
        except voluptuous.Invalid as e:
            print(f"Warning: invalid command spec {path}: {e}")
            return None

        return spec["commands"]

    def get_mod(self, name: str) -> Optional[ModuleType]:
        if name not in self._installed:
            print(f"Warning: plugin {name} is not installed")
            return None

        plugin = self._installed[name]

        try:
            module = plugin.load()
        except Exception as e:
            print(f"Warning: error loading plugin {name}: {e}")
            return None

        return module

    def _load(self, name: str):
        module = self.get_mod(name)
        if module is None:
            print(f"Skipping requested plugin {name}")
            return None

        if not hasattr(module, "commands"):
            print(f"Warning: skipping plugin {name} since it does not define commands")
            return None

        return getattr(module, "commands")


# TODO: we'll probably want to construct this in the tclint entry point and pass
# it around rather than using a singleton instance, but this made for an easier
# refactor.
PluginManager = _PluginManager()
