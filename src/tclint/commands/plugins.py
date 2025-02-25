from importlib_metadata import entry_points
import json
import pathlib
from typing import Dict, Optional, List
from types import ModuleType


class _PluginManager:
    def __init__(self):
        self._loaded = {}
        self._installed = {}
        self._command_specs = {}
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
            plugin_name = spec["plugin"]
        except KeyError:
            print(f"Warning: invalid command spec {path}, missing key 'plugin'")
            return None

        module = self.get_mod(plugin_name)
        if module is None:
            return None

        try:
            command_spec = spec["spec"]
        except KeyError:
            print(f"Warning: invalid command spec {path}, missing key 'spec'")
            return None

        if not hasattr(module, "commands_from_spec"):
            print(
                f"Warning: command spec provided for {plugin_name} but this plugin "
                "doesn't support command specs"
            )
            return None

        commands_from_spec = getattr(module, "commands_from_spec")
        return commands_from_spec(command_spec)

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

    def load_command_specs(self, command_specs: List[pathlib.Path]):
        for spec_file in command_specs:
            try:
                with open(spec_file, "r") as f:
                    spec = json.load(f)
            except FileNotFoundError:
                print(f"Spec file {spec_file} not found, skipping...")
                continue

            try:
                plugin_name = spec["plugin"]
            except KeyError:
                print(f"Invalid spec file {spec_file}, missing key 'plugin'")
                continue

            try:
                command_spec = spec["spec"]
            except KeyError:
                print(f"Invalid spec file {spec_file}, missing key 'spec'")
                continue

            if plugin_name in self._command_specs:
                print(
                    f"Warning: overwriting existing spec for {plugin_name} with"
                    f" {spec_file}"
                )
            self._command_specs[plugin_name] = command_spec

    def _load(self, name: str):
        module = self.get_mod(name)
        if module is None:
            print(f"Skipping requested plugin {name}")
            return None

        if name in self._command_specs:
            if not hasattr(module, "commands_from_spec"):
                print(
                    f"Warning: skipping plugin {name}: associated spec file provided"
                    " but plugin doesn't support spec files"
                )
                return None

            commands_from_spec = getattr(module, "commands_from_spec")
            return commands_from_spec(self._command_specs[name])

        if not hasattr(module, "commands"):
            print(
                f"Warning: skipping plugin {name} since no spec was provided and it"
                " does not define commands"
            )
            return None

        return getattr(module, "commands")


# TODO: we'll probably want to construct this in the tclint entry point and pass
# it around rather than using a singleton instance, but this made for an easier
# refactor.
PluginManager = _PluginManager()
