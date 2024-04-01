# Violations

This page lists all lint violations that may be reported by `tclint`.

- [`indent`](#indent)
- [`spacing`](#spacing)
- [`line-length`](#line-length)
- [`trailing-whitespace`](#trailing-whitespace)
- [`blank-lines`](#blank-lines)
- [`command-args`](#command-args)
- [`redefined-builtin`](#redefined-builtin)
- [`backslash-spacing`](#backslash-spacing)
- [`expr-format`](#expr-format)
- [`spaces-in-braces`](#spaces-in-braces)
- [`unbraced-expr`](#unbraced-expr)

Each of these violations is sorted into one of two coarse categories, which can
be displayed using the `--show-categories` CLI option.

- `func`: violations that may impact the script's functionality
- `style`: style-related violations with no functional impact

## `indent`

Source files must be indented consistently. `tclint` requires an additional level of indentation within script arguments (e.g. the body of an `if` or `while` command), as well as for continuations of command arguments.

The one configurable exception is the `namespace eval` command. If `style.indent-namespace-eval` is false, then the body of this command doesn't need an extra level of indentation. The default is true.

The indentation style can be configured using `style.indent`. The default is 4 spaces. Tabs and spaces may never be mixed.

### Rationale

Consistent indentation enhances readability.

## `spacing`

There must be one space between the arguments of a command.

`tclint` allows one configurable exception to this rule. It's a common pattern to align the values of `set` blocks with names that have different lengths, for example:

```tcl
set foo  1
set barx 2
```

If `style.allow-aligned-sets` is true, `tclint` will not report spacing violations for contiguous blocks of sets that conform to this style. This is off by default: this style is not recommended for new scripts since it makes updating code more difficult and pollutes version control diffs.

## `line-length`

Lines must not exceed a maximum line length, configurable by `style.line-length`. The default is 80 characters.

Lines that contain URLs are ignored, since these can't be broken nicely.

### Rationale

Long lines inhibit readability, particularly on small monitors or split panes.

## `trailing-whitespace`

Lines must not include trailing whitespace.

### Rationale

Trailing whitespace is rarely semantically meaningful and often pollutes version control diffs.

## `blank-lines`

Scripts may not contain too many consecutive blank lines. This number can be configured by `style.max-blank-lines`.

### Rationale

Blank lines can be used to visually organize code and enhance readability. However, an excessive number unecessarily increases file length and may result in inconsistent visual organization, decreasing readability.

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

## `backslash-spacing`

Backslashes used to split a command over multiple lines should be separated from line contents by one space.

### Rationale

Consistent spacing enhances readability.

## `expr-format`

Components of expressions must be formatted according to the following rules:

- Binary and ternary operations have one space between operators and operands
- Unary operations have no space between the operator and operand
- Functions must be formatted like so: `max($a, $b, ...)`

Note that more style rules may be enforced as `expr-format` violations in future releases.

### Rationale

Consistent formatting enhances readability.

## `spaces-in-braces`

The spacing around the contents of braced expression or script arguments must be consistent. If `style.spaces-in-braces` is true, `tclint` expects one space between the contents of a braced argument and the braces themselves. If `style.spaces-in-braces` is false, `tclint` expects no spaces between the contents and the braces.

For example:

```tcl
# style.spaces-in-braces = True
for { set i 0 } { $i < 10 } { incr i } {
    puts $i
}

# style.spaces-in-braces = False
for {set i 0} {$i < 10} {incr i} {
    puts $i
}
```

### Rationale

Consistent formatting enhances readability.

## `unbraced-expr`

Expressions that contain substitutions should be enclosed by braces.

### Rationale

Without braces, the Tcl parser will perform substitutions before interpreting
the expression. This is not actually the desired behavior in most cases, and may
impact functionality in some edge cases. In addition, this can reduce
performance.

See "Performance Considerations" in the [Tcl docs for `expr`](https://www.tcl.tk/man/tcl/TclCmd/expr.html).
