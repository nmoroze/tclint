from pathlib import Path
import sys

import pytest

from tclint.cli.utils import make_exclude_filter


# These are not regularly run in CI, but were run at time of check-in. Keeping them
# around for reference.
@pytest.mark.skipif(
    sys.platform != "win32", reason="testing edge cases with Windows path handling"
)
@pytest.mark.parametrize(
    "pattern,path,root,excluded",
    [
        ("foo.tcl", "C:\\foo.tcl", "D:\\", True),
        ("foo.tcl", "C:\\blah.tcl", "D:\\", False),
        ("../foo.tcl", "C:\\foo.tcl", "D:\\", False),
        ("/foo.tcl", "C:\\foo.tcl", "D:\\", False),
    ],
)
def test_exclude_filter_windows(pattern, path, root, excluded):
    is_excluded = make_exclude_filter([pattern], Path(root))
    assert is_excluded(Path(path)) == excluded
