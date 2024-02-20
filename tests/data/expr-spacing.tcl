expr {max($a, $b) > $c ?  $a : $b}
if {1>0} {}
if {$bool_a || \
    $bool_b} {
}

expr {![foo]}
expr {~ [bar]}

expr {max($a, $b, $c)}
expr {max ( $a , $b,  $c )}
