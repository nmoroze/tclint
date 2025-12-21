# Command Plugins

Many systems extend Tcl with custom commands (e.g. EDA tools or programs like Expect).
`tclint` supports a command plugin system that allows it to check that scripts use these
commands correctly.

## Writing Plugins

Plugins can be specified in one of two ways:

1) [Statically](#static-plugins), using a JSON file.
2) [Dynamically](#dynamic-plugins), as a Python module.


### Static Plugins

The top-level schema of a JSON plugin looks like the following:

```jsonc
{
    // Plugin name.
    "name": "<name>",
    // Dictionary mapping command names to "command specs".
    "commands": {
        "command1": { /* ... */ },
        "command2": { /* ... */ },
        // ...
    }
}
```

Command specs define what arguments may be passed to a command.
Arguments fall into two categories, `switches` or `positionals`.

Switches generally start with `-` and will be parsed anywhere in the argument list.
They're specified under the `"switches"` key in the argument spec as a dictionary mapping switch names to info about the argument.
For example:

```jsonc
{
    "switches": {
        "-switch": {
            // Whether the switch must be supplied.
            "required": false,
            // Whether the switch may be supplied more than once.
            "repeated": false,
            // Value the switch takes. May be `null` if it takes no value.
            "value": {"type": "any"},
            // Optional, name to use for value in error or help messages.
            // E.g. `-switch <value>`.
            "metavar": "value",
        }
    }
}
```

Positionals are arguments that are parsed in the order they appear in the argument list.
They're specified under the `"positionals"` key.
For example:

```jsonc
{
    "positionals": [
        {
            // Name of argument. May be used in error or help messages.
            "name": "arg1",
            // Whether the argument must be supplied.
            "required": true,
            // Type of argument value. May be `{"type": "variadic"}` if
            // argument may be an infinite number of args.
            "value": {"type": "any"},
        },
    ],
}
```

Here's the command spec for a subset of the `create_clock` SDC command:

```jsonc
/*
create_clock
    -period period_value
    [-add]
    [source_objects]
*/
{
    "create_clock": {
        "switches": {
            "-period": {
                "required": true,
                "repeated": false,
                "value": {"type": "any"},
                "metavar": "period_value"
            },
            "-add": {
                "required": false,
                "repeated": false,
                "value": null,
            }
        },
        "positionals": [
            {
                "name": "source_objects",
                "required": false,
                "value": {"type": "any"}
            }
        ]
    }
}
```

#### Skipping Validation

To specify commands in a plugin without providing info about their arguments, provide `null` in place of the command spec.
This makes it easy to create lightweight plugins that tell `tclint` about a command for checks like `redefined-builtin` without having to fully specify its arguments.

#### Subcommands

Specify the subcommands of a command by supplying a dictionary keyed with `"subcommands"`.
For example:

```jsonc
{
    "dict": {
        "subcommands": {
            "append": { /* ... */ }, // Command spec, or {"subcommands": ...}.
            "create": { /* ... */ },
            // ...
        }
    }
}
```

### Dynamic Plugins

Dynamic plugins provide more functionality than static plugins.
They support validating a command's expected arguments using Python code, and support transforming the parse tree by performing additional parsing of a command's arguments.

While they can do more than static plugins, dynamic plugins have some pitfalls.
If a static plugin can support your use case, write one of those instead.
It's easy to convert a static plugin to a dynamic one if you later decide the extra functionality is necessary.

Dynamic plugins are defined as Python modules with a top-level dictionary attribute `commands`.
Each key is the name of a command, and the associated value is either a command handler function or a command spec dictionary (as defined in [Static Plugins](#static-plugins)).

The following is a simple example:

```python
"""Example dynamic plugin defining two commands, `simple` and `complex`."""
from tclint.commands.checks import arg_count, CommandArgError

commands = {
    "simple": {
        "switches": {},
        "positionals" [{"name": "arg", "value": {"type": "any"}, "required": True}],
    },
    "complex": _complex,
}

def _complex(args, parser):
    """complex [key value...] body"""
    count, has_arg_exp = arg_count(args, parser)

    # count is only valid if has_arg_exp is False.
    if not has_arg_exp and count % 2 == 0:
        raise CommandArgError("expected odd number of arguments")

    if len(args) < 1:
        raise CommandArgError("expected at least one argument")

    return args[:-1] + parser.parse_script(args[-1])
```

While parsing source files, `tclint` calls each handler every time it encounters an instance of the associated command.
A command handler takes in two arguments:
1) The arguments to the command as a list of syntax tree nodes (subclasses of [`tclint.syntax_tree.Node`][syntax_tree]).
2) An instance of [`tclint.parser.Parser`][parser] that can be used for parsing the contents of the nodes.

If the handler returns a list of nodes, `tclint` will update the parse tree, replacing the command's arguments with those nodes.
If the handler returns `None`, the arguments of the command will remain as-is.

To indicate that the user has supplied invalid arguments to the command, raise an instance of [`tclint.commands.checks.CommandArgError`][checks] with a helpful error message.

#### Best practices
- In most cases, prefer using [`tclint.commands.checks.arg_count(args, parser)`][checks] over `len(args)` for validating argument counts.

[syntax_tree]: ../src/tclint/syntax_tree.py
[parser]: ../src/tclint/parser.py
[checks]: ../src/tclint/commands/checks.py

## Using Plugins

There are several ways to actually check a tool-specific script using a plugin. The
simplest is to pass the command spec to `tclint` via `--commands`:

```shell
tclint or_place.tcl --commands openroad.json
```

> [!NOTE]
> For security reasons, you can't provide a path to a dynamic plugin Python file via a config file.
> These paths must be provided on the CLI using `--commands` instead.

[openroad]: https://github.com/The-OpenROAD-Project/OpenROAD
