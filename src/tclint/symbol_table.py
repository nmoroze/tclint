import logging
from collections import defaultdict
from typing import List

from tclint.syntax_tree import BareWord, VarSub, Visitor, Command, Node


class SymbolTable:
    """Holds a symbol table (definition & references of symbols)."""

    KEYS = ("proc", "var")

    def __init__(self):
        self.sym_def = {k: defaultdict(list) for k in self.KEYS}
        self.sym_ref = {k: defaultdict(list) for k in self.KEYS}

    def add_proc_reference(self, name: str, command: Command) -> None:
        logging.debug(f"Reference to proc {name} at {command._pos_str()}")
        self.sym_ref["proc"][name].append((command.pos, command.end_pos))

    def add_var_reference(self, name: str, var_sub: VarSub) -> None:
        logging.debug(f"Reference to var {name} at {var_sub._pos_str()}")
        self.sym_ref["var"][name].append((var_sub.pos, var_sub.end_pos))

    def add_definition(self, sym_type: str, command: Command) -> None:
        if len(command.args) == 0:
            return

        def_node = command.args[0]
        name = def_node.contents
        logging.debug(f"Definition of {sym_type} {name} at {def_node._pos_str()}")
        self.sym_def[sym_type][name].append((def_node.pos, def_node.end_pos))

    def lookup(self, node: Node, table: dict):
        ts = self.type_and_symbol(node)
        if ts is None:
            return []
        key, word = ts

        logging.debug(f"Lookup {key} definition of '{word}'")

        if word not in table[key]:
            return []
        return table[key][word]

    def lookup_definition(self, node: Node) -> List[tuple[tuple, tuple]]:
        return self.lookup(node, self.sym_def)

    def lookup_references(self, node: Node) -> List[tuple[tuple, tuple]]:
        return self.lookup(node, self.sym_ref)

    def type_and_symbol(self, node: Node) -> tuple[str, str] | None:
        """Get symbol type and symbol text to look for from the node under the cursor."""
        # "proc foo" with cursor over "proc"
        if (
            isinstance(node, BareWord)
            and node.value == "proc"
            and isinstance(node.next, BareWord)
        ):
            return "proc", node.next.value
        # "proc foo" with cursor over "foo"
        if (
            isinstance(node, BareWord)
            and isinstance(node.prev, BareWord)
            and node.prev.value == "proc"
            and node.value is not None
        ):
            return "proc", node.value
        # "foo" as first word in a statement
        if (
            isinstance(node, BareWord)
            and node.prev is None
            and node.value is not None
            and node.value != "set"
        ):
            return "proc", node.value

        # "set foo" with cursor over "set"
        if (
            isinstance(node, BareWord)
            and node.value == "set"
            and isinstance(node.next, BareWord)
        ):
            return "var", node.next.value
        # "set foo" with cursor over "foo"
        if (
            isinstance(node, BareWord)
            and isinstance(node.prev, BareWord)
            and node.prev.value == "set"
            and node.value is not None
        ):
            return "var", node.value
        # "$foo"
        if isinstance(node, VarSub) and node.value is not None:
            return "var", node.value


class SymbolTableBuilder(Visitor):
    """Builds a symbol table."""

    def __init__(self):
        self.table = SymbolTable()

    def build(self, tree) -> SymbolTable:
        """Run the builder visitor through the syntax tree, building a table."""
        tree.accept(self, recurse=True)
        return self.table

    def visit_command(self, command: Command):
        key = command.routine.contents
        if key == "set":
            self.table.add_definition("var", command)
        elif key == "proc":
            self.table.add_definition("proc", command)
        else:
            self.table.add_proc_reference(key, command)

    def visit_var_sub(self, var_sub: VarSub):
        key = var_sub.value
        if key is None:
            logging.warning(f"VarSub without value at {var_sub._pos_str()}")
            return
        self.table.add_var_reference(key, var_sub)
