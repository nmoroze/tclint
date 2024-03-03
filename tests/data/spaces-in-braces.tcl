if 1 {
}

if {$foo} {
}

expr { $foo }
expr {$foo}

expr { 5 + 2 * 3 - 4 ? "foo" : true}

# quoted things are not checked, this is okay
for "set i 0" " 1 " "incr i  " {
}

# args interpreted as scripts also checked
for { set i 0} {$i < 5 } { incr i  } {
}
