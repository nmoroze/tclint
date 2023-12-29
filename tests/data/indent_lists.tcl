# Apply only needs 1 level of indentation

# good
apply {{a b c} {
    puts "$a $b $c"
}} {*}$foo

# bad
apply {{a b c} {
        puts "$a $b $c"
}} {*}$foo

# good: normal switch formatting
switch $args {
    {a} {
        puts "A"
    } {b} {
        puts "B"
    }
}

# good: "folded" switch style
switch $args {{a} {
    puts "A"
} {b} {
    puts "B"
}
} ;# extra NL before close brace is currently OK, but I prefer it on prev line

# bad: newline at start of list requires extra indent
switch $args {
{a} {
    puts "A"
}}

# TODO: check format of proc args
proc foo {
    alpha beta charlie
} {
    puts "$alpha $beta $charlie"
}