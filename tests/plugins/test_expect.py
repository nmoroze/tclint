import pytest

# Not clean, but we import the _PluginManager class instead of using the singleton so we
# have isolation between tests.
from tclint.commands.plugins import _PluginManager as PluginManager
from tclint.parser import Parser


def test_load():
    # This will fail if tclint is not installed in your environment.
    assert PluginManager().load("expect") is not None


@pytest.mark.parametrize("command", ["close", "close -i $spawn_id"])
def test_parse_valid(command):
    parser = Parser(command_plugins=["expect"])
    parser.parse(command)
    assert len(parser.violations) == 0, f"unexpected violation: {parser.violations[0]}"
