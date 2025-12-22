import codecs
from collections import defaultdict
import os
from pathlib import Path
import re
from typing import Callable, List

import pathspec

from tclint.config import (
    ExcludePattern,
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
