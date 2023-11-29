for {set i 1}  {$i < 100} {incr i} {
if {[expr $i % 15] == 0} {
puts "FizzBuzz"
}   elseif {[expr $i % 3] == 0} {
        puts "Fizz"
} elseif {[expr $i % 5] == 0} {
        puts   "Buzz"
    } else {
        puts     $i
    }
}
