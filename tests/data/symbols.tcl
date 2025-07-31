# simple function
proc hello_world { } {
  puts "Hello, world!"
}

# function with arguments
proc print_foobar { val_foo val_bar } {
  puts "(inside fn) foo: $val_foo, bar: $val_bar"
}

hello_world

set val_foo "Blub"
set val_bar "Blah"

print_foobar Foo Bar

puts "(outside fn) foo: $val_foo, bar: $val_bar"

# to check multiple references
hello_world
