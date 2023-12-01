# Configuration

`tclint` is configured via a [TOML](https://toml.io/en/) configuration file.

The following fields are supported:

```toml
# paths to exclude when searching directories. defaults to empty list.
exclude = ["ignore_me/", "ignore.tcl"]
# lint violations to ignore. defaults to empty list.
ignore = ["spacing"]

[style]
# number of spaces to indent. can also be set to "tab". defaults to 4.
indent = 2
# maximum allowed line length. defaults to 80.
line-length = 100
# whether to allow values of set blocks to be aligned. defaults to false.
allow-aligned-sets = true
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
