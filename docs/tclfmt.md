# tclfmt

`tclfmt` is a formatter for Tcl scripts. It automatically reformats Tcl code using a
consistent style, and can be used to enforce this style in a shared codebase.

## Usage

The simplest way to use `tclfmt` is to provide the path of a Tcl source file as a
positional argument:

```sh
tclfmt example.tcl
```

This prints the reformatted contents of `example.tcl` to stdout.

To automatically update a script's formatting, provide the `--in-place` option:

```sh
# modifies example.tcl
tclfmt --in-place example.tcl
```

You can also pass multiple paths to `tclfmt`, including directories. `tclfmt` collects
files the same way as `tclint`.

Run `tclfmt --help` for a full list of command line arguments.

### Configuration

`tclfmt` reads `tclint` configuration files. It finds these files in the same way as
`tclint`, and the fields are interpreted the same by both tools. The exceptions are the
following fields, which are ignored by `tclfmt`:

- `ignore`
- `style.line-length`
- `style.allow-aligned-sets`

### Enforcing style in CI

`tclfmt` can be used in continuous integration systems to enforce that all Tcl scripts
in a codebase are formatted with a consistent style.

The recommended approach is to use the `--check` flag, which will exit with a non-zero
status code if any file would be reformatted by `tclfmt`. This mode also outputs which
files requires reformatting.

```sh
tclfmt --check .
```

If using `tclfmt` alongside `tclint`, you can disable `tclint`'s style checks by passing
`--no-check-style`. `tclfmt` provides more comprehensive checking than `tclint`, and
skipping the redundant checks will reduce output noise. `tclfmt` is the recommended
approach for enforcing style going forward, and `tclint`'s style checks will eventually
be deprecated.

## Guarantees

`tclfmt` only formats code; it does not modify code in any that changes its meaning. If
`tclfmt` has modified the functionality of your code, this is a bug. Please [open an
issue][issue] with a reproducible test case if you believe this has happened.

`tclfmt` was released recently, so we recommend careful review of code that's been
modified directly by the tool. Another way to check `tclfmt`'s work is to run it in
debug mode by providing `-d`. In debug mode, `tclfmt` will parse code again after
formatting and ensure that its syntax tree matches the original.

`tclfmt`'s output is stable. That means if you run `tclfmt` on code already formatted by
`tclfmt`, it will stay the same.

## Style

This section describes major aspects of the style used by `tclfmt`. It also gives
rationale for certain decisions.

### Indentation

`tclfmt` adds one level of indentation to:

- Scripts passed to commands (e.g. the body of an `if` or `proc` command)
- Continuations of commands onto additional lines
- Multi-line expressions or lists
- Function arguments or parenthesized subexpressions that continue onto additional lines
(within expressions)

`tclfmt` does not maintain visually aligned indentation. For example,

```tcl
command arg1 \
        arg2 \
        arg3
```

is reformatted as

```tcl
command arg1 \
    arg2 \
    arg3
```

This style reduces line length in most cases. It also reduces noise in version control
diffs, since unrelated lines don't have to change to fix alignment when the command
name is updated.

`tclfmt` puts the braces of multi-line expressions and lists onto their own lines in
order to facilitate this indentation style. For example,

```tcl
if {$cond1 && $cond2 &&
    $cond3} {
    puts "true"
}
```

is reformatted as

```tcl
if {
    $cond1 && $cond2 &&
    $cond3
} {
    puts "true"
}
```

Although this style may add extra lines compared to alternatives, it ensures that the
bodies of control-flow commands are visually distinct from conditional expressions, no
matter the command or indentation size. For example, in the unformatted snippet above
you can see that `$cond3` and `puts` are at the same indentation level on consecutive
lines, which could make them appear to be part of the same block when quickly skimming
code. `tclfmt`'s formatting fixes this.

Multiline command substitutions are indented, but `tclfmt` preserves opening and closing
brackets that are on the same lines as the command:

```tcl
set foo [command \
    arg]
```

However, if the command substitution contains multiple commands, then the brackets are
forced onto separate lines, in order to make this case visually distinct. For example,

```tcl
set foo [command1
    command2]
```

is reformatted as

```tcl
set foo [
    command1
    command2
]
```

### Line length

`tclfmt` does not (yet) reformat lines to stay under a certain length. However, it
respects existing line breaks in the code, adjusting indentation as needed.

`tclint` reports a `line-length` violation on lines that are too long. Since `tclfmt`
can't fix these violations, they're still reported even when `tclint` is run with
`--no-check-style`. When it makes sense, consider reducing line length by factoring out
subcomponents of complicated expressions or commands rather than just adding line
breaks. For example:

```tcl
puts "Here is the result of a really long command: [really_long_command arg1 arg2]""
```

could be refactored to

```tcl
set result [really_long_command arg1 arg2]
puts "Here is the result of a really long command: $result"
```

### Spacing

`tclfmt` emits one space between all words in a command. This means that `tclfmt` will
not preserve visually aligned arguments of consecutive commands. For example,

```tcl
set abcdef 1
set hijkl  2
set mnop   3
```

is reformatted as

```tcl
set abcdef 1
set hijkl 2
set mnop 3
```

This style reduces noise in version control diffs, since unrelated lines don't have
to change to fix alignment when other lines are updated.

### Spurious whitespace

`tclfmt` trims down sets of blank lines to no more than two. It also removes blank lines
at the beginning and end of script bodies. In most instances, `tclfmt` removes trailing
whitespace at the end of lines.

Note that in some cases trailing whitespace may be semantically meaningful, in which
case `tclfmt` won't remove it. However, this whitespace is often unintentional and may
even cause bugs (for example, whitespace that comes after a `\` that was meant to be a
newline escape). In order to catch this, `tclint` will flag violations on trailing
whitespace even when provided `--no-check-style`.

### Command separators and comments

`tclfmt` removes unnecessary semicolons, relying on line breaks as command separators.
When a comment is on the same line as a command, `tclfmt` combines the semicolon and
hash and emits one space before the comment. For example:

```tcl
command ;# This comment documents that command
```

[issue]: https://github.com/nmoroze/tclint/issues/new