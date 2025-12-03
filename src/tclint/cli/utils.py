import codecs
from collections import defaultdict
import os
from pathlib import Path
import re
from typing import Callable, List, Optional

import pathspec

from tclint.config import (
    Config,
    ExcludePattern,
    load_config_at,
)


def register_codec_warning(name):
    def replace_with_warning_handler(e):
        # TODO: formal warning mechanism, include path
        print("Warning: non-unicode characters in file, replacing with �")
        return codecs.replace_errors(e)

    codecs.register_error(name, replace_with_warning_handler)


def make_exclude_filter(
    exclude_patterns: List[ExcludePattern],
) -> Callable[[Path], bool]:
    # Transform patterns into a data structure keyed on root.
    patterns_by_root = defaultdict(list)
    for pattern, root in exclude_patterns:
        # I think this is escaping #, which would otherwise be treated like a comment.
        # Not 100% sure though, I originally wrote this a while ago.
        pattern = re.sub(r"^\s*#", r"\#", pattern)
        patterns_by_root[root.resolve()].append(pattern)

    compiled_patterns = {}
    for root in patterns_by_root.keys():
        patterns = patterns_by_root[root]
        spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        compiled_patterns[root] = spec

    def is_excluded(path: Path) -> bool:
        abspath = path.resolve()

        for root, exclude_spec in compiled_patterns.items():
            try:
                relpath = Path(os.path.relpath(abspath, start=root))
            except ValueError:
                # We get here if path and exclude_root are on different drives (on
                # Windows).Things should still behave roughly as expected without
                # using a relative path. See
                # test_cli_utils.py::test_exclude_filter_windows for test cases.
                relpath = abspath

            if exclude_spec.match_file(relpath):
                return True
        return False

    return is_excluded


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
        self, paths: List[Path], cwd: Path
    ) -> List[tuple[Optional[Path], Config]]:
        sources: List[tuple[Optional[Path], Config]] = []

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
