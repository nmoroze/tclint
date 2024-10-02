# tclint-disable unbraced-expr
expr $foo
# tclint-enable unbraced-expr

# tclint-disable-next-line unbraced-expr, redundant-expr
expr { [expr $foo] }

puts too many arguments ! ;# tclint-disable-line command-args

# tclint-disable
expr { [expr $foo] }
# tclint-enable
