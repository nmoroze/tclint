from tclint.commands.checks import (
    CommandArgError,
)


def _foo(args, parser):
    raise CommandArgError("foo")


commands = {
    "foo": _foo,
}
