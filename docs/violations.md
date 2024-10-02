# Violations

This page lists all lint violations that may be reported by `tclint`.

- [`line-length`](#line-length)
- [`trailing-whitespace`](#trailing-whitespace)
- [`command-args`](#command-args)
- [`redefined-builtin`](#redefined-builtin)
- [`unbraced-expr`](#unbraced-expr)
- [`redundant-expr`](#redundant-expr)

## `line-length`

Lines must not exceed a maximum line length, configurable by `style.line-length`. The default is 80 characters.

Lines that contain URLs are ignored, since these can't be broken nicely.

### Rationale

Long lines inhibit readability, particularly on small monitors or split panes.

## `trailing-whitespace`

Lines must not include trailing whitespace.

### Rationale

Trailing whitespace is rarely semantically meaningful and often pollutes version control diffs. In cases where it is semantically meaningful, it can cause bugs (for example, trailing whitespace after a backslash that's meant to be a newline escape).

## `command-args`

Commands must be called with appropriate arguments. The exact reason for this violation being reported will be command-specific, but the following are common scenarios:

- Invalid argument count
- Invalid subcommand
- Ambiguous script arguments (e.g. `tclint` is unable to parse `if {1} $body`)

### Rationale

Incorrect use of commands can result in runtime errors, and ambiguous script arguments limit `tclint`'s ability to fully check code that may be executed at runtime.

## `redefined-builtin`

`proc` definitions may not use the name of built-in commands.

### Rationale

Redefining built-in commands can lead to confusion and result in `tclint`
reporting false positive `command-args` violations.

## `unbraced-expr`

- Expressions that contain substitutions should be enclosed by braces.
- Expressions that contain braced or quoted words should be enclosed by braces.

### Rationale

#### Expressions containing substitutions

Without braces, the Tcl parser will perform substitutions before interpreting
the expression. This is not actually the desired behavior in most cases, and may
impact functionality in some edge cases. In addition, this can reduce
performance.

See "Performance Considerations" in the [Tcl docs for `expr`](https://www.tcl.tk/man/tcl/TclCmd/expr.html).

#### Expressions containing braced or quoted words

The contents of braced or quoted words will be "un-quoted" and interpreted directly as
part of the expression, which is different from how they'd be interpreted if the entire
expression was braced. In most cases, this is not the author's intent.

Note that both of the above cases also limit `tclint` and `tclfmt`'s ability to properly
parse, lint, and format code.

## `redundant-expr`

`expr` command substitutions shouldn't be used in contexts that are already interpreted as
an expression, for example:

```tcl
# BAD: inner [expr ...] is unnecessary!
if {[expr $foo % 2] == 0} {
    # ...
}

# GOOD
if {$foo % 2 == 0} {
    # ...
}
```

### Rationale

These command substitutions are redundant, which inhibits readability and may negatively
impact performance.
