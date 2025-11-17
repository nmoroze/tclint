from tclint.commands.checks import (
    CommandArgError,
)
from tclint.commands.schema import commands_schema


def _foo(args, parser):
    raise CommandArgError("foo")


commands = commands_schema({
    "foo": _foo,
})
