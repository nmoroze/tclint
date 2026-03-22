# Bad: missing space before quote
utl::warn DPL 343"-disallow_one_site_gaps is deprecated"
# Bad: missing open quote
test_cmd -arg1 $param1"
# Bad: quote in middle of word
puts h"llo
# Good: properly quoted (should NOT trigger)
puts "hello world"
# Good: escaped quote in bare word (should NOT trigger)
puts hello\"world
# Good: escaped quote inside double quotes (should NOT trigger)
puts "hello\"world"
