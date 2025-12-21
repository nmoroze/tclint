# tclint &nbsp; [![CI](https://github.com/nmoroze/tclint/actions/workflows/ci.yml/badge.svg)](https://github.com/nmoroze/tclint/actions/workflows/ci.yml)

`tclint` is a collection of modern dev tools for Tcl. It includes a linter, a formatter, and a language server that provides Tcl support to your editor of choice.

### Features

- [Editor integration][lsp] for VS Code, Neovim, and Emacs
- [Linting][violations] for common Tcl errors
- [Formatter][tclfmt] that enforces a consistent, readable style
- [Plugin system](docs/plugins.md) that supports Tcl variants
- [More features][features] coming soon!

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

Aspects of `tclint`'s behavior can be controlled by a configuration file.
By default, `tclint` will search for a file named `tclint.toml` or `.tclint` by walking the parent directories of source files, but a path to an alternate configuration file can be provided using the `-c` or `--config` flag.
See [Configuration](docs/configuration.md) for documentation on the configuration file.

`tclint` includes a plugin system for checking EDA tool-specific commands. See the [Plugins](docs/plugins.md) documentation page for more info.

## Contributing

`tclint` welcomes community contributions. The best way to help the project is to [open an issue](https://github.com/nmoroze/tclint/issues/new) if you find a bug or have a feature request.

PRs are also welcome, but for non-trivial changes please open an issue first to solicit feedback. This helps avoid wasted effort.

Use the following steps to set up `tclint` for local development:

```sh
$ git clone https://github.com/nmoroze/tclint.git # or URL to fork
$ cd tclint
$ python3 -m venv .venv # set up a venv to ensure clean environment
$ source .venv/bin/activate
(venv) $ pip install --upgrade pip # development requires pip >= 25.1
(venv) $ pip install -e . --group dev
```

Please format, lint, and run tests before submitting changes:

```sh
$ source .venv/bin/activate
(venv) $ black .
(venv) $ ./util/pre-commit
```

## License

This project is copyright Noah Moroze, released under the [MIT license](LICENSE).

[vscode]: https://marketplace.visualstudio.com/items?itemName=nmoroze.tclint
[violations]: docs/violations.md
[lsp]: docs/lsp.md
[tclfmt]: docs/tclfmt.md
[features]: https://github.com/nmoroze/tclint/issues/91
