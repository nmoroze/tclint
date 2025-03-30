# Command Plugins

EDA tools generally extend their embedded Tcl shells with custom tool-specific commands.
`tclint` supports a command plugin system that allows it to check that scripts use these
commands correctly.

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
