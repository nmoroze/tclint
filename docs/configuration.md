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
# number of spaces to indent. can also be set to "tab". defaults to 4.
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

## Filesets

The configuration file can define an arbitrary number of sub-configurations that apply to a specific set of paths. These sub-configs support the same set of fields as the global configuration, with the exception of `exclude` and `extensions`.

The following example shows how to add two fileset sub-configs that each override different configuration fields:

```toml
[[fileset]]
paths = ["other_file_group1/"]
ignore = ["command-args"]

[fileset.style]
indent = 3

[[fileset]]
paths = ["other_file_group2/"]

[fileset.style]
spaces-in-braces = false
```

At the moment, if a file being linted matches more than one fileset, `tclint` will use the configuration in the first fileset that applies.

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