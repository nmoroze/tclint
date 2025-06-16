# Command Plugins

EDA tools generally extend their embedded Tcl shells with custom tool-specific commands.
`tclint` supports a command plugin system that allows it to check that scripts use these
commands correctly.

## Writing Plugins

Plugins can be specified in one of two ways:

1) Statically, using a JSON file.
2) Dynamically, as a Python module.

For now, this documentation only describes the first case.

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

## Using Plugins

There are several ways to actually check a tool-specific script using a plugin. The
simplest is to pass the command spec to `tclint` via `--commands`:

```shell
tclint or_place.tcl --commands openroad.json
```

For codebases that contain scripts for multiple tools, it's best to use a configuration
file that defines multiple filesets. For example, for a codebase like:

```
├── openroad_scripts/
├── other_scripts/
└── tclint.toml
```

You might add the following section to `tclint.toml`:

```toml
[[fileset]]
paths = ["openroad_scripts/"]
commands = "~/.tclint/openroad.json"
```
[openroad]: https://github.com/The-OpenROAD-Project/OpenROAD
