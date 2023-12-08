# Configuration

`tclint` is configured via a [TOML](https://toml.io/en/) configuration file.

The following example shows all supported fields:

```toml
# paths to exclude when searching directories. defaults to empty list.
exclude = ["ignore_me/", "ignore.tcl"]
# lint violations to ignore. defaults to empty list.
# can also supply an inline table with a path and a list of violations to ignore under that path.
ignore = [
    "spacing",
    { path = "files_with_bad_indent/", rules = ["indent"] }
]

[style]
# number of spaces to indent. can also be set to "tab". defaults to 4.
indent = 2
# maximum allowed line length. defaults to 80.
line-length = 100
# whether to allow values of set blocks to be aligned. defaults to false.
allow-aligned-sets = true
```

## Filesets

The configuration file can define an arbitrary number of sub-configurations that apply to a specific set of paths. These sub-configs support the same set of fields as the global configuration, with the exception of `exclude`.

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
allow-aligned-sets = false
```

At the moment, if a file being linted matches more than one fileset, `tclint` will use the configuration in the first fileset that applies.

## CLI arguments

Each configuration field supports at least one command line argument that can be used to override its value. Values supplied using these switches always override values supplied in the config file, with the exception of `--extend-exclude` and `--extend-ignore`, which extends any previously configured list with the supplied values.

```
configuration arguments:
  --ignore "rule1, rule2, ..."
  --extend-ignore "rule1, rule2, ..."
  --exclude "path1, path2, ..."
  --extend-exclude "path1, path2, ..."
  --style-indent <indent>
  --style-line-length <line_length>
  --style-aligned-sets
  --style-no-aligned-sets
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
# tclint-disable spacing
puts  "illegal"
# tclint-enable spacing

# tclint-disable-next-line indent, spacing
  puts  "also illegal"

puts too many arguments ! ;# tclint-disable-line command-args

# tclint-disable
 puts  "illegal"
# tclint-enable
```


## `pyproject.toml`

`tclint` can also be configured by a `pyproject.toml` file, under the `[tool.tclint]` key. For example:

```toml
[build-system]
requires = ["setuptools"]

# other tables/keys...

[tool.tclint]
ignore = ["spacing"]

[tool.tclint.style]
indent = 2
```

Configuration in a `pyproject.toml` is lowest priority, and only checked if neither default config path exists. The file will be ignored if it contains TOML syntax errors.

[eslint-comments]: https://eslint.org/docs/latest/use/configure/rules#using-configuration-comments-1