# tclint &nbsp; [![CI](https://github.com/nmoroze/tclint/actions/workflows/ci.yml/badge.svg)](https://github.com/nmoroze/tclint/actions/workflows/ci.yml)

`tclint` is a lint tool for Tcl. It analyzes Tcl source files and reports issues that may cause bugs, inhibit readability, or affect performance.

### Features

- Checks for common Tcl errors
- Companion formatting utility, [`tclfmt`](docs/tclfmt.md)
- Usage checks for built-in commands
- Visual Studio Code [extension][vscode]
- [Plugin system](docs/plugins.md) for usage checks of EDA tool-specific commands, including [OpenROAD][openroad]
- More coming soon!

## Getting Started

Install `tclint` from PyPI using [`pipx`](https://pypa.github.io/pipx/) (recommended):

```sh
pipx install tclint
```

Or with `pip`:

```sh
pip install tclint
```

Run `tclint` on a Tcl source file by providing its path as a positional argument:

```sh
tclint example.tcl
```

If the file contains any lint violations, they will be printed and `tclint` will return a non-zero exit code. Otherwise, the output will be empty and `tclint` will exit successfully.

### Example

```console
$ cat example.tcl
if { [expr {$input > 10}] } {
  puts $input is greater than 10!
}
$ tclint example.tcl
data/example.tcl:1:6: unnecessary command substitution within expression [redundant-expr]
data/example.tcl:2:3: too many args for puts: got 5, expected no more than 3 [command-args]
```

## Usage

`tclint` is a command-line utility. It takes a list of paths as positional arguments, which may either be direct paths to source files, or directories which will be recursively searched for files ending in `.tcl`, `.sdc`, `.xdc`, or `.upf`.

Collected files will be checked for lint violations.  See the
[Violations](docs/violations.md) documentation page for a description of all
lint violations `tclint` may report.

Aspects of `tclint`'s behavior can be controlled by a configuration file. By default, `tclint` will look for a file named `tclint.toml` or `.tclint` in the current working directory (in that order), but a path to an alternate configuration file can be provided using the `-c` or `--config` flag. See [Configuration](docs/configuration.md) for documentation on the configuration file.

`tclint` includes a plugin system for checking EDA tool-specific commands. See the [Plugins](docs/plugins.md) documentation page for more info.

## Contributing

`tclint` welcomes community contributions. The best way to help the project is to [open an issue](https://github.com/nmoroze/tclint/issues/new) if you find a bug or have a feature request.

PRs are also welcome, but for non-trivial changes please open an issue first to solicit feedback. This helps avoid wasted effort.

Use the following steps to set up `tclint` for local development:

```sh
$ git clone https://github.com/nmoroze/tclint.git # or URL to fork
$ cd tclint
$ pip install -e .[dev]
```

Please format, lint, and run tests before submitting changes:

```sh
$ black --preview .
$ ./util/pre-commit
```

## License

This project is copyright Noah Moroze, released under the [MIT license](LICENSE).

[openroad]: https://github.com/The-OpenROAD-Project/OpenROAD
[vscode]: https://marketplace.visualstudio.com/items?itemName=nmoroze.tclint
