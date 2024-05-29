from tclint.plugins.openroad.help_parser import (
    parse_help_entry,
    make_spec,
    Command,
    Switch,
    OptionalArg,
    Positional,
    AnyVal,
    ExclusiveArgs,
    ExclusiveVals,
    Literal,
    ListVal,
)


def test_basic_help():
    tree = parse_help_entry("command -switch [optional] positional")
    expected = Command(
        "command",
        [
            Switch("-switch"),
            OptionalArg(Positional(AnyVal("optional"))),
            Positional(AnyVal("positional")),
        ],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive():
    tree = parse_help_entry("estimate_parasitics -placement|-global_routing")
    expected = Command(
        "estimate_parasitics",
        [
            ExclusiveArgs([
                Switch("-placement"),
                Switch("-global_routing"),
            ])
        ],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_mixed_keys():
    tree = parse_help_entry("command [-foo foo | -bar | -baz baz]")
    expected = Command(
        "command",
        [
            OptionalArg(
                ExclusiveArgs([
                    Switch("-foo", AnyVal("foo")),
                    Switch("-bar"),
                    Switch("-baz", AnyVal("baz")),
                ])
            )
        ],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_literal():
    tree = parse_help_entry("command -switch a|b|c")
    expected = Command(
        "command",
        [Switch("-switch", ExclusiveVals([Literal("a"), Literal("b"), Literal("c")]))],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_literal_parens_spaces():
    tree = parse_help_entry("command -switch ( a|b |c)")
    expected = Command(
        "command",
        [Switch("-switch", ExclusiveVals([Literal("a"), Literal("b"), Literal("c")]))],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_careted_metavar():
    tree = parse_help_entry("define_pdn_grid [-name <name>]")
    expected = Command(
        "define_pdn_grid", [OptionalArg(Switch("-name", AnyVal("<name>")))]
    )
    assert tree == expected, f"{tree} != {expected}"


def test_list():
    tree = parse_help_entry("density_fill -area {lx ly ux uy}")
    expected = Command(
        "density_fill", [Switch("-area", ListVal(["lx", "ly", "ux", "uy"]))]
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_any_list():
    tree = parse_help_entry("improve_placement -max_displacement disp|{disp_x disp_y}")
    expected = Command(
        "improve_placement",
        [
            Switch(
                "-max_displacement",
                ExclusiveVals([AnyVal("disp"), ListVal(["disp_x", "disp_y"])]),
            )
        ],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_list_any():
    tree = parse_help_entry("improve_placement -max_displacement {disp_x disp_y}|disp")
    expected = Command(
        "improve_placement",
        [
            Switch(
                "-max_displacement",
                ExclusiveVals([ListVal(["disp_x", "disp_y"]), AnyVal("disp")]),
            )
        ],
    )
    assert tree == expected, f"{tree} != {expected}"


def test_exclusive_optionals():
    tree = parse_help_entry("command [-foo] | [-bar]")
    spec = make_spec(tree)

    assert "-foo" in spec and spec["-foo"] == {
        "repeated": False,
        "required": False,
        "value": False,
    }
    assert "-bar" in spec and spec["-bar"] == {
        "repeated": False,
        "required": False,
        "value": False,
    }


def test_parenthesized_args():
    help = "command [(-foo|-bar)]"
    tree = parse_help_entry(help)
    expected = Command(
        "command", [OptionalArg(ExclusiveArgs([Switch("-foo"), Switch("-bar")]))]
    )
    assert tree == expected, f"{tree} != {expected}"
