import pytest

from tclint.commands.plugins import PluginManager
from tclint.parser import Parser


def test_load():
    # This will fail if tclint is not installed in your environment.
    assert PluginManager().load("expect") is not None


@pytest.mark.parametrize("command", ["close", "close -i $spawn_id"])
def test_parse_valid(command):
    plugins = PluginManager()
    parser = Parser(commands=plugins.get_commands(["expect"]))
    parser.parse(command)
    assert len(parser.violations) == 0, f"unexpected violation: {parser.violations[0]}"
