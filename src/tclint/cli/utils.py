import codecs
import os
import pathlib
import re
from typing import List, Optional

import pathspec


def register_codec_warning(name):
    def replace_with_warning_handler(e):
        # TODO: formal warning mechanism, include path
        print("Warning: non-unicode characters in file, replacing with �")
        return codecs.replace_errors(e)

    codecs.register_error(name, replace_with_warning_handler)


def make_exclude_filter(exclude_patterns: List[str]):
    exclude_patterns = [
        re.sub(r"^\s*#", r"\#", pattern) for pattern in exclude_patterns
    ]
    exclude_spec = pathspec.PathSpec.from_lines("gitwildmatch", exclude_patterns)

    def is_excluded(path: pathlib.Path, root: pathlib.Path) -> bool:
        abspath = path.resolve()
        root = root.resolve()

        try:
            relpath = pathlib.Path(os.path.relpath(abspath, start=root))
        except ValueError:
            # We get here if path and exclude_root are on different drives (on Windows).
            # Things should still behave roughly as expected without using a relative
            # path. See test_cli_utils.py::test_exclude_filter_windows for test cases.
            relpath = abspath

        if exclude_spec.match_file(relpath):
            return True
        return False

    return is_excluded


def resolve_sources(
    paths: List[pathlib.Path],
    exclude_patterns: List[str],
    exclude_root: pathlib.Path,
    extensions: List[str],
) -> List[Optional[pathlib.Path]]:
    """Resolves paths passed via CLI to a list of filepaths to lint.

    `paths` is a list of paths that may be files or directories. Files are
    returned verbatim if they exist, and directories are recursively searched
    for files that have an extension specified in `extensions`. Paths that match a
    pattern in `exclude_patterns` are ignored (based on gitignore pattern
    format, see https://git-scm.com/docs/gitignore#_pattern_format).

    Raises FileNotFoundError if a supplied path does not exist.
    """
    extensions = [f".{ext}" if not ext.startswith(".") else ext for ext in extensions]
    is_excluded = make_exclude_filter(exclude_patterns)

    sources: List[Optional[pathlib.Path]] = []

    for path in paths:
        if str(path) == "-":
            sources.append(None)
            continue

        if not path.exists():
            raise FileNotFoundError(f"path {path} does not exist")

        if is_excluded(path, exclude_root):
            continue

        if not path.is_dir():
            sources.append(path)
            continue

        for dirpath, _, filenames in os.walk(path):
            for name in filenames:
                _, ext = os.path.splitext(name)
                if ext.lower() in extensions:
                    child = pathlib.Path(dirpath) / name
                    if not is_excluded(child, exclude_root):
                        sources.append(child)

    return sources
