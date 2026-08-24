# tclint-disable unbraced-expr
expr $foo
# tclint-enable unbraced-expr

# tclint-disable-next-line unbraced-expr, redundant-expr
expr { [expr $foo] }

puts too many arguments ! ;# tclint-disable-line command-args

# tclint-disable
expr { [expr $foo] }
# tclint-enable

# Configuration comment descriptions: everything after "--" is a note for
# humans and must not be parsed as a rule name.
# tclint-disable unbraced-expr -- rules, then a description
expr $foo
# tclint-enable unbraced-expr

# tclint-disable -- description only, no rule list
expr { [expr $foo] }
# tclint-enable -- and on the enable side too

expr { [expr $foo] } ;# tclint-disable-line -- description only

expr { [expr $foo] } ;# tclint-disable-line redundant-expr,unbraced-expr -- ok

# tclint-disable-next-line -- description only
expr { [expr $foo] }
