import logging
from collections import defaultdict
from typing import List, DefaultDict, Union

from tclint.syntax_tree import Visitor, Command, CommandSub, Node, Script


class SymbolTable:
    """Holds a symbol table (links symbols to nodes)."""

    def __init__(self):
        self.proc_def: DefaultDict[str, list[Node]] = defaultdict(list)

    def add_proc_definition(self, command: Command) -> None:
        """Add definition of procedure"""
        # command holds the "proc" keyword, so the proc name is 1st argument
        proc_name_node = command.args[0]
        proc_name = proc_name_node.contents
        if not proc_name:
            return
        logging.debug(
            f"Definition of proc '{proc_name}' at {proc_name_node._pos_str()}"
        )
        self.proc_def[proc_name].append(proc_name_node)

    def lookup_proc_definitions(self, symbol_text: str) -> List[Node]:
        """Lookup definitions of the procedure pointed at by node"""
        if symbol_text is None or symbol_text not in self.proc_def:
            return []
        return self.proc_def[symbol_text]


class SymbolTableBuilder(Visitor):
    """Builds a symbol table."""

    def __init__(self):
        self.table = SymbolTable()

    def build(self, tree: Union[CommandSub, Script]) -> SymbolTable:
        """Run the builder visitor through the syntax tree, building a table."""
        tree.accept(self, recurse=True)
        return self.table

    def visit_command(self, command: Command) -> None:
        if command.routine.contents == "proc":
            self.table.add_proc_definition(command)
