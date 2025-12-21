# Configuration

`tclint` is configured via a [TOML](https://toml.io/en/) configuration file.

The following example shows all supported fields:

```toml
# patterns to exclude when searching directories. defaults to empty list.
# follows gitignore pattern format: https://git-scm.com/docs/gitignore#_pattern_format
# the one exception is that a leading "#" character will be automatically escaped
exclude = ["ignore_me/", "ignore*.tcl", "/ignore_from_here"]
# lint violations to ignore. defaults to empty list.
ignore = ["unbraced-expr"]
# extensions of files to lint when searching directories. defaults to tcl, sdc,
# xdc, and upf.
extensions = ["tcl"]
# path to command spec defining tool-specific commands and arguments.
commands = "~/.tclint/openroad.json"

# with the exception of line-length, the [style] settings affect tclfmt rather than tclint.

[style]
# number of spaces to indent. can also be set to "tab", or "mixed",<s>,<t>. defaults to 4.
indent = 2
# maximum allowed line length. defaults to 100.
line-length = 80
# maximum allowed number of consecutive blank lines. defaults to 2.
max-blank-lines = 1
# whether to require indenting of "namespace eval" blocks. defaults to true.
indent-namespace-eval = false
# whether to expect a single space (true) or no spaces (false) surrounding the contents of a braced expression or script argument.
# defaults to false.
spaces-in-braces = true
```

## Config discovery

All tools in the `tclint` family discover configuration files by searching for files named `tclint.toml`, `.tclint`, or `pyproject.toml` in the directories above each analyzed source file.
The configuration closest to a given source file is the one that gets applied.
For example, if a project structure looks like the following:

```
├── scripts/
├──── tclint.toml -> applies to bar.tcl
├──── bar.tcl
├── tclint.toml -> applies to foo.tcl
└── foo.tcl
```

Then the configuration in `scripts/tclint.toml` applies to `scripts/bar.tcl`, and the configuration in `tclint.toml` applies to `foo.tcl`.

`tclint` will search for config files up to the root of the filesystem, and config files will be resolved the same even if `tclint` is run within a subdirectory of a project.

If multiple config files appear in a given directory, a file is picked according to this priority order:
1) `tclint.toml`
2) `.tclint`
3) `pyproject.toml` (special case, see [here](#pyproject.toml) for more info)

If `tclint` is traversing a directory to discover source files, it will load each config file it finds and apply the `exclude` and `extensions` settings as it further traverses the filesystem.

All relative paths and exclude patterns that appear in config files are resolved relative to the parent directory of that config file.
The exception are config files specified directly using `-c` or `--config`, in which case the paths are resolved relative to the current working directory.

## CLI arguments

Each configuration field supports at least one command line argument that can be used to override its value. Values supplied using these switches always override values supplied in the config file, with the exception of `--extend-exclude` and `--extend-ignore`, which extends any previously configured list with the supplied values.

```
configuration arguments:
  --ignore "rule1, rule2, ..."
  --extend-ignore "rule1, rule2, ..."
  --exclude "pattern1, pattern2, ..."
  --extend-exclude "pattern1, pattern2, ..."
  --extensions "tcl, xdc, ..."
  --commands <path>
  --style-line-length <line_length>
```

## Ignore violations with inline comments

Lint violations can be ignored in-line by adding comments with special keywords. All of the supported keywords may be followed by a comma-separated list of rules. If no rules are specified, the effect will apply to all rules.

The following lists supported keywords. These keywords were inspired by [ESLint][eslint-comments].

- `tclint-disable <rules>`
  - Specified violations will be ignored until they are re-enabled by a `tclint-enable` comment (or end-of-file is reached).
- `tclint-disable-line <rules>`
  - Specified violations will be ignored for the line on which this comment appears.
- `tclint-disable-next-line <rules>`
  - Specified violations will be ignored for the line following the one on which this comment appears.
- `tclint-enable <rules>`
  - Any specified violations which have previously been disabled by `tclint-disable` will be re-enabled.

### Example

```tcl
# tclint-disable unbraced-expr
expr $foo
# tclint-enable unbraced-expr

# tclint-disable-next-line unbraced-expr, redundant-expr
expr { [expr $foo] }

puts too many arguments ! ;# tclint-disable-line command-args

# tclint-disable
expr { [expr $foo] }
# tclint-enable
```


## `pyproject.toml`

`tclint` can also be configured by a `pyproject.toml` file, under the `[tool.tclint]` key. For example:

```toml
[build-system]
requires = ["setuptools"]

# other tables/keys...

[tool.tclint]
ignore = ["unbraced-expr"]

[tool.tclint.style]
indent = 2
```

Configuration in a `pyproject.toml` is lowest priority, and only checked if neither default config path exists. The file will be ignored if it contains TOML syntax errors.

[eslint-comments]: https://eslint.org/docs/latest/use/configure/rules#using-configuration-comments-1