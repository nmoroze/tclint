import logging
from collections import defaultdict

from tclint.syntax_tree import (
    Visitor,
    Command,
)


class SymbolTable:
    """Holds a symbol table (definition & references of symbols)."""

    KEYS = ("proc", "set")

    def __init__(self):
        self.sym_def = {k: defaultdict(list) for k in self.KEYS}
        self.sym_ref = {k: defaultdict(list) for k in self.KEYS}

    def add_command(self, key: str, command: Command) -> None:
        if key not in self.KEYS:
            return

        if len(command.args) == 0:
            # This is a syntax error, just ignore it
            return

        name = command.args[0].contents

        logging.debug(f"Definition of {key}: {name} at: {command._pos_str()}")
        self.sym_def[key][name].append((command.pos, command.end_pos))

    def lookup_definition(self, word: str) -> tuple[tuple, tuple] | None:
        logging.debug(f"Lookup definition of {word}")
        if word not in self.sym_def["proc"]:
            return None
        defs = self.sym_def["proc"][word]
        if len(defs) > 1:
            logging.warning(f"Multiple definitions ({len(defs)}) of '{word}'")
        return defs[0]


class SymbolTableBuilder(Visitor):
    """Builds a symbol table."""

    def __init__(self):
        self.table = SymbolTable()

    def build(self, tree):
        tree.accept(self, recurse=True)

    def visit_command(self, command: Command):
        key = command.routine.contents
        self.table.add_command(key, command)
