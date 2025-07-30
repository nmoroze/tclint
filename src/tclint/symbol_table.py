import logging
from collections import defaultdict
from typing import List

from tclint.syntax_tree import (
    VarSub,
    Visitor,
    Command,
)


class SymbolTable:
    """Holds a symbol table (definition & references of symbols)."""

    KEYS = ("proc", "set")

    def __init__(self):
        self.sym_def = {k: defaultdict(list) for k in self.KEYS}
        self.sym_ref = {k: defaultdict(list) for k in self.KEYS}

    def add_proc_reference(self, key: str, command: Command) -> None:
        logging.debug(f"Reference to proc {key} at: {command._pos_str()}")
        self.sym_ref["proc"][key].append((command.pos, command.end_pos))

    def add_var_reference(self, key: str, var_sub: VarSub) -> None:
        logging.debug(f"Reference to var {key} at: {var_sub._pos_str()}")
        self.sym_ref["set"][key].append((var_sub.pos, var_sub.end_pos))

    def add_command(self, key: str, command: Command) -> None:
        if key not in self.KEYS:
            return self.add_proc_reference(key, command)

        if len(command.args) == 0:
            # This is a syntax error, just ignore it
            return

        name = command.args[0].contents

        logging.debug(f"Definition of {key}: {name} at: {command._pos_str()}")
        self.sym_def[key][name].append((command.pos, command.end_pos))

    def lookup_definition(self, word: str) -> tuple[tuple, tuple] | None:
        logging.debug(f"Lookup definition of {word}")
        if word.startswith("$"):
            key = "set"
            word = word[1:]
        else:
            key = "proc"

        if word not in self.sym_def[key]:
            return None
        defs = self.sym_def[key][word]
        if len(defs) > 1:
            logging.warning(f"Multiple definitions ({len(defs)}) of '{word}'")
        return defs[0]

    def lookup_references(self, word: str) -> List[tuple[tuple, tuple]] | None:
        logging.debug(f"Lookup references of {word}")
        if word not in self.sym_ref["proc"]:
            return None
        return self.sym_ref["proc"][word]


class SymbolTableBuilder(Visitor):
    """Builds a symbol table."""

    def __init__(self):
        self.table = SymbolTable()

    def build(self, tree):
        tree.accept(self, recurse=True)

    def visit_command(self, command: Command):
        key = command.routine.contents
        self.table.add_command(key, command)

    def visit_var_sub(self, var_sub: VarSub):
        key = var_sub.value
        if key is None:
            logging.warning(f"VarSub without value at {var_sub._pos_str()}")
            return
        self.table.add_var_reference(key, var_sub)
