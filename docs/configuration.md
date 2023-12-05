# Configuration

`tclint` is configured via a [TOML](https://toml.io/en/) configuration file.

The following fields are supported:

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