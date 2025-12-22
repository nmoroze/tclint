import os
from pathlib import Path
from typing import Optional

from tclint.config import (
    Config,
    load_config_at,
)
from tclint.cli.utils import make_exclude_filter


class Resolver:
    def __init__(self, cli_args=None, global_config: Optional[Config] = None):
        # TODO: Figure out a way to annotate cli_args type effectively.
        self._config_cache: dict[Path, Config] = {}
        self._global_config = global_config

        # Instantiate and hang on to a default config so the Resolver can cache many
        # instances of it without blowing up memory footprint.  (This has not been
        # empirically validated!)
        self._default_config = Config()
        self._cli_args = None
        if cli_args is not None:
            self._default_config.apply_cli_args(cli_args)
            self._cli_args = cli_args

    def _find_config(self, directory: Path) -> Config:
        config = load_config_at(directory)
        if config is not None:
            if self._cli_args is not None:
                config.apply_cli_args(self._cli_args)
            return config

        # We're at the root, bail!
        if directory.parent == directory:
            return self._default_config

        return self.find_config(directory.parent)

    def find_config(self, directory: Path) -> Config:
        if self._global_config is not None:
            return self._global_config

        if directory in self._config_cache:
            return self._config_cache[directory]
        config = self._find_config(directory)
        self._config_cache[directory] = config
        return config

    def resolve_sources(
        self, paths: list[Path], cwd: Path
    ) -> list[tuple[Optional[Path], Config]]:
        sources: list[tuple[Optional[Path], Config]] = []

        for path in paths:
            if str(path) == "-":
                config = self.find_config(cwd)
                sources.append((None, config))
                continue

            if not path.exists():
                raise FileNotFoundError(f"path {path} does not exist")

            # We need to slap a .resolve() on the find_config()'s to make sure the
            # method traverses upwards to the FS root. It would probably ideal to just
            # resolve each path in the main body of the loop, but this actually has
            # implications on how the filepath is printed out (it becomes an absolute
            # path, symlinks are resolved).

            if not path.is_dir():
                config = self.find_config(path.resolve().parent)
                is_excluded = make_exclude_filter(config.exclude)
                if is_excluded(path):
                    continue
                sources.append((path, config))
                continue

            for dirstr, dirs, filenames in os.walk(path):
                dirpath = Path(dirstr)
                config = self.find_config(dirpath.resolve())
                is_excluded = make_exclude_filter(config.exclude)
                extensions = [
                    f".{ext}" if not ext.startswith(".") else ext
                    for ext in config.extensions
                ]

                # Update dirs to prune next directories to traverse based on exclude.
                to_traverse = []
                for dir in dirs:
                    if not is_excluded(Path(dir)):
                        to_traverse.append(dir)
                dirs[:] = to_traverse

                for name in filenames:
                    _, ext = os.path.splitext(name)
                    if ext.lower() in extensions:
                        child = dirpath / name
                        if not is_excluded(child):
                            sources.append((child, config))

        return sources
