from pathlib import Path

# Not clean, but we import the _PluginManager class instead of using the singleton so we
# have isolation between tests.
from tclint.commands.plugins import _PluginManager as PluginManager

MY_DIR = Path(__file__).parent.resolve()
TEST_DATA_DIR = MY_DIR / "data"


def test_load_openroad():
    plugins = PluginManager()
    loaded = plugins.load_from_spec(TEST_DATA_DIR / "openroad.json")
    assert isinstance(loaded, dict)


def test_load_invalid():
    plugins = PluginManager()
    loaded = plugins.load_from_spec(TEST_DATA_DIR / "invalid.json")
    assert loaded is None


def test_load_py():
    plugins = PluginManager()
    loaded = plugins.load_from_py(TEST_DATA_DIR / "dynamic.py")
    assert isinstance(loaded, dict)


def test_load_py_invalid():
    plugins = PluginManager()
    loaded = plugins.load_from_py(TEST_DATA_DIR / "dynamic_invalid.py")
    assert loaded is None
