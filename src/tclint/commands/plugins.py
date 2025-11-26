from importlib_metadata import entry_points
import json
import pathlib
from typing import Dict, Optional
from types import ModuleType
from importlib.util import spec_from_file_location, module_from_spec

import voluptuous

from tclint.commands import schema


class _PluginManager:
    def __init__(self):
        self._loaded = {}
        self._installed = {}
        self._loaded_specs = {}
        self._loaded_py = {}
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
            # expanduser() may raise RuntimeError
            print(f"Warning: command spec {path} not found, skipping...")
            return None
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"Warning: {path} contains invalid JSON: {e}, skipping...")
            return None

        try:
            # Apply defaults and validate the spec.
            spec = schema.schema(spec)
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

    def _load_module(self, name, module):
        if module is None:
            print(f"Skipping requested plugin {name}")
            return None

        if not hasattr(module, "commands"):
            print(f"Warning: skipping plugin {name} since it does not define commands")
            return None

        spec = getattr(module, "commands")
        try:
            # Apply defaults and validate the spec.
            spec = schema.commands_schema(spec)
        except voluptuous.Invalid as e:
            print(f"Warning: invalid plugin {name}: {e}")
            return None

        return spec

    def _load(self, name: str):
        module = self.get_mod(name)
        return self._load_module(name, module)

    def load_from_py(self, path: pathlib.Path) -> Optional[Dict]:
        if path in self._loaded_py:
            return self._loaded_py[path]

        spec = self._load_from_py(path)
        self._loaded_py[path] = spec
        return spec

    def _load_from_py(self, path: pathlib.Path) -> Optional[Dict]:
        mod = None
        name = path.stem

        try:
            spec = spec_from_file_location(name, path)
            if spec is not None:
                mod = module_from_spec(spec)
                if spec.loader is not None:
                    spec.loader.exec_module(mod)
        except FileNotFoundError:
            print(f"Warning: command spec {path} not found, skipping...")
            return None
        except Exception as e:
            print(f"Warning: error loading plugin {path}: {e}")
            return None

        return self._load_module(name, mod)


# TODO: we'll probably want to construct this in the tclint entry point and pass
# it around rather than using a singleton instance, but this made for an easier
# refactor.
PluginManager = _PluginManager()
