from pathlib import Path

from tclint.symbol_table import SymbolTable, SymbolTableBuilder
import tclint.syntax_tree as ast
from tclint.parser import Parser

MY_DIR = Path(__file__).parent.resolve()


def test_symtab_builder():
    source_text = Path(MY_DIR / "data" / "symbols.tcl").read_text()
    tree = Parser().parse(source_text)
    symtab = SymbolTableBuilder().build(tree)

    hello_world = symtab.lookup_proc_definitions("hello_world")
    assert len(hello_world) == 1
    assert hello_world[0].pos == (2, 6)


def test_static_proc_name():
    symtab = SymbolTable()
    command = ast.Command(
        ast.BareWord("proc"), ast.BareWord("foo"), ast.List(), ast.Script()
    )
    symtab.add_proc_definition(command)

    foo = symtab.lookup_proc_definitions("foo")
    assert len(foo) == 1
    assert foo[0].value == "foo"


def test_dynamic_proc_name():
    symtab = SymbolTable()
    # Result of parsing `proc $name {} {}`
    command = ast.Command(
        ast.BareWord("proc"), ast.VarSub("name"), ast.List(), ast.Script()
    )
    symtab.add_proc_definition(command)

    assert symtab.lookup_proc_definitions("name") == []
    assert symtab.lookup_proc_definitions("$name") == []
