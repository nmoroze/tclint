 puts "violation 1"

if {1} {
   puts "violation 2"
        puts "violation 3"
     # comments also must follow rules
}

if {1} {puts "same line okay"}

# same here:
puts "a"; puts "b"

command1 \
-arg1 \
    -arg2

switch $arg {
        "a" {
        puts "a"
    }
"b" {
    puts "b"
    }
    }
