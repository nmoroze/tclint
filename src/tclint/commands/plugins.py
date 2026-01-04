import json
import pathlib
from collections.abc import Sequence
from importlib.util import module_from_spec, spec_from_file_location
from types import ModuleType
from typing import Optional

import voluptuous
from importlib_metadata import entry_points

from tclint.commands import builtin as _builtin
from tclint.commands import schema


class PluginManager:
    def __init__(self, trust_uninstalled=False):
        self._loaded = {}
        self._installed = {}
        self._loaded_specs = {}
        self._loaded_py = {}
        for plugin in entry_points(group="tclint.plugins"):
            if plugin.name in self._installed:
                print(f"Warning: found duplicate definitions for plugin {plugin.name}")
            self._installed[plugin.name] = plugin

        self._trust_uninstalled = trust_uninstalled

    def load(self, name: str) -> Optional[dict]:
        if name in self._loaded:
            return self._loaded[name]

        mod = self._load(name)
        self._loaded[name] = mod
        return mod

    def load_from_spec(self, path: pathlib.Path) -> Optional[dict]:
        if path in self._loaded_specs:
            return self._loaded_specs[path]

        spec = self._load_from_spec(path)
        self._loaded_specs[path] = spec
        return spec

    def _load_from_spec(self, path: pathlib.Path) -> Optional[dict]:
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

    def load_from_py(self, path: pathlib.Path) -> Optional[dict]:
        if path in self._loaded_py:
            return self._loaded_py[path]

        # By default, reject paths to dynamic plugins. This restriction is designed to
        # make it explicit when tclint is executing external code.
        if not self._trust_uninstalled:
            print(
                f"Warning: skipping untrusted plugin {path}. If you trust the code at"
                " this path, re-run with --trust-plugins to load the plugin"
            )
            return None

        spec = self._load_from_py(path)
        self._loaded_py[path] = spec
        return spec

    def _load_from_py(self, path: pathlib.Path) -> Optional[dict]:
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

    def get_commands(self, plugins: Sequence[str | pathlib.Path]) -> dict:
        commands = {}
        commands.update(_builtin.commands)

        for plugin in plugins:
            if isinstance(plugin, str):
                plugin_commands = self.load(plugin)
            elif isinstance(plugin, pathlib.Path):
                if plugin.suffix == ".py":
                    plugin_commands = self.load_from_py(plugin)
                else:
                    plugin_commands = self.load_from_spec(plugin)
            else:
                raise TypeError(f"Plugins must be strings or paths, got {type(plugin)}")

            if plugin_commands is not None:
                commands.update(plugin_commands)

        return commands
