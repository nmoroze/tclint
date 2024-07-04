import re

from tclint.commands import get_commands
from tclint.violations import Rule, Violation

from tclint.syntax_tree import Visitor, Script, List, ParenExpression, BracedExpression


class IndentLevelChecker(Visitor):
    """Checks that each line is indented at the correct level.

    Reports 'indent' violations.
    """

    def __init__(self):
        # -1 lets us add 1 in all script visitors and get the correct level in
        # the top-level script
        self.level = -1

        # maps lines to expected indent levels
        self.expected_levels = {}

    def check(self, input, tree, config):
        self._is_namespace_eval = False
        self._indent_namespace_eval = config.style_indent_namespace_eval

        # first have visitor calculate expected indent on each line
        tree.accept(self, recurse=False)

        # then iterate line-by-line to verify that actual indentation matches
        violations = []
        for lineno, line in enumerate(input.split("\n")):
            # 1-indexed
            lineno += 1

            if lineno not in self.expected_levels:
                continue
            if self.expected_levels[lineno] is None:
                continue

            expected_level = self.expected_levels[lineno]
            indent = "\t" if config.style_indent == "tab" else " " * config.style_indent
            expected_indent = indent * expected_level

            actual_indent = ""
            for c in line:
                if c in {" ", "\t"}:
                    actual_indent += c
                else:
                    break

            if expected_indent != actual_indent:
                if config.style_indent == "tab":
                    expected_str = (
                        f"{expected_level} tab{'s' if expected_level != 1 else ''}"
                    )
                else:
                    count = expected_level * config.style_indent
                    expected_str = f"{count} space{'s' if count != 1 else ''}"

                if " " in actual_indent and "\t" in actual_indent:
                    actual_str = "mix of tabs and spaces"
                elif "\t" in actual_indent:
                    actual_str = f"{len(actual_indent)}"
                    if config.style_indent != "tab":
                        actual_str += f" tab{'s' if len(actual_indent) != 1 else ''}"
                else:
                    actual_str = f"{len(actual_indent)}"
                    if config.style_indent == "tab":
                        actual_str += f" space{'s' if len(actual_indent) != 1 else ''}"

                pos = (lineno, 1)
                violations.append(
                    Violation(
                        Rule.INDENT,
                        f"expected indent of {expected_str}, got {actual_str}",
                        pos,
                    )
                )

        return violations

    def visit_script(self, script):
        should_indent = not self._is_namespace_eval or self._indent_namespace_eval
        self._visit_block(script, should_indent=should_indent)

    def visit_list(self, list):
        # lists work a bit like scripts. However, they only add a level of
        # indentation when there's a newline between the end and start of an
        # item in the list (or between the start of the list and the first
        # element). This seems to be a good standard for enforcing conventional
        # formatting in a couple different contexts, e.g. switch and apply. See
        # tests/data/indent_lists.tcl for test cases that exercise this logic.

        should_indent = False

        prev_line = list.line
        for child in list.children:
            if prev_line is not None and prev_line != child.line:
                should_indent = True
                break
            prev_line = child.end_pos[0]

        self._visit_block(list, should_indent=should_indent)

    def _visit_block(self, block, should_indent=True):
        if should_indent:
            self._incr_level()
        for child in block.children:
            child.accept(self)
        if should_indent:
            self._decr_level()

        # check indentation of closing token of script
        if block.end_pos:
            end_line, _ = block.end_pos
            if end_line not in self.expected_levels:
                self.expected_levels[end_line] = self.level

    def visit_command(self, command):
        assert len(command.children) > 0

        if command.line in self.expected_levels:
            # already visited something on this line
            # TODO: do we want to return here? do we still wanna check continuation?
            return

        prev_namespace_eval = self._is_namespace_eval
        self._is_namespace_eval = (
            command.routine == "namespace"
            and len(command.args) > 0
            and command.args[0].contents == "eval"
        )

        self.expected_levels[command.line] = self.level

        for child in command.children:
            # continuations of command must be indented. If the node is a list
            # or script however, the indentation only applies to contents of that node
            # (handled by the relevant visitors)
            if not isinstance(child, (Script, List)):
                self._incr_level()

            child.accept(self)

            if not isinstance(child, (Script, List)):
                self._decr_level()

        self._is_namespace_eval = prev_namespace_eval

    def visit_comment(self, comment):
        self._set_level(comment)

    def visit_command_sub(self, command_sub):
        self._set_level(command_sub)

    def visit_bare_word(self, word):
        self._set_level(word)

    def visit_braced_word(self, word):
        self._set_level(word)

        # Ensure that we don't check indentation of things that come after closing
        # brace, if this is closed on a different line than it starts.
        end_line = word.end_pos[0]
        if end_line not in self.expected_levels:
            self.expected_levels[end_line] = None

    def visit_quoted_word(self, word):
        self._set_level(word)

    def visit_compound_bare_word(self, word):
        self._set_level(word)

    def visit_var_sub(self, var_sub):
        self._set_level(var_sub)

    def visit_arg_expansion(self, arg_expansion):
        self._set_level(arg_expansion)

    def visit_expression(self, expression):
        self._visit_expression(expression)

    def visit_braced_expression(self, expression):
        self._visit_expression(expression)

    def _visit_expression(self, expression):
        prev_level = self.level
        # don't check indents for things under expression
        self.level = None
        for child in expression.children:
            child.accept(self, recurse=True)
        self.level = prev_level

    def _set_level(self, node):
        if node.line in self.expected_levels:
            return

        self.expected_levels[node.line] = self.level

    def _incr_level(self):
        if self.level is None:
            return
        self.level += 1

    def _decr_level(self):
        if self.level is None:
            return
        self.level -= 1


class SpacingChecker(Visitor):
    """Ensures each word of a command is separated by a single space (if on the
    same line).

    Reports 'spacing' violations.
    """

    def __init__(self):
        self.violations = []
        self.set_groups = [
            []
            # [set cmd...]
        ]

    def check(self, _, tree, config):
        self.aligned_set = config.style_allow_aligned_sets

        tree.accept(self, recurse=True)

        if self.aligned_set:
            self._check_set_spacing()

        return self.violations

    def visit_command(self, command):
        if len(command.args) == 0:
            return

        handle_as_aligned_set = command.routine == "set" and self.aligned_set

        last_word = command.children[0]
        for i, word in enumerate(command.children[1:]):
            if last_word.end_pos[0] != word.pos[0]:
                # ignore if on diff lines
                last_word = word
                continue

            if handle_as_aligned_set and i == 1:
                # relies on visit_command being called in order
                if (
                    len(self.set_groups[-1]) > 0
                    and command.line == self.set_groups[-1][-1].line + 1
                ):
                    self.set_groups[-1].append(command)
                else:
                    self.set_groups.append([command])

                continue

            spacing = word.pos[1] - last_word.end_pos[1]
            if spacing != 1:
                self.violations.append(
                    Violation(
                        Rule.SPACING,
                        f"expected 1 space between words, got {spacing}",
                        last_word.end_pos,
                    )
                )
            last_word = word

    def _check_set_spacing(self):
        for group in self.set_groups:
            furthest_value_start = 0
            for cmd in group:
                value_start = cmd.args[1].pos[1]
                if value_start > furthest_value_start:
                    furthest_value_start = value_start

            violations = []
            all_aligned = True
            for cmd in group:
                if cmd.args[1].pos[1] != furthest_value_start:
                    all_aligned = False

                spacing = cmd.args[1].pos[1] - cmd.args[0].end_pos[1]
                if spacing != 1:
                    violations.append(
                        Violation(
                            Rule.SPACING,
                            "expected 1 space between value and name or fully aligned"
                            " block",
                            cmd.args[1].pos,
                        )
                    )

            # If all set values are aligned, waive violations. Alignment is
            # meaningless if there's only one command in the group, always
            # report in that case.
            if len(group) == 1 or not all_aligned:
                self.violations.extend(violations)

    def visit_binary_op(self, binary_op):
        return self._check_op_spacing(binary_op)

    def visit_ternary_op(self, ternary_op):
        return self._check_op_spacing(ternary_op)

    def _check_op_spacing(self, expression):
        last_child = expression.children[0]
        for child in expression.children[1:]:
            if last_child.end_pos[0] != child.pos[0]:
                # ignore if on diff lines
                last_child = child
                continue

            # TODO: collapse to one violation for multiple violations in one expression
            spacing = child.pos[1] - last_child.end_pos[1]
            if spacing != 1:
                self.violations.append(
                    Violation(
                        Rule.EXPR_FORMAT,
                        "expected 1 space between operands and operators in expression",
                        last_child.end_pos,
                    )
                )

            last_child = child

    def visit_paren_expression(self, expression):
        assert len(expression.children) == 1
        child = expression.children[0]

        if isinstance(child, ParenExpression):
            # check for doubly-nested parens, e.g. `((foo))`
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "unecessary set of parentheses around expression",
                    expression.pos,
                )
            )

        # TODO: collapse to one violation if both errors present
        if (
            expression.pos[0] == child.pos[0]
            and (child.pos[1] - expression.pos[1]) != 1
        ):
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "expected no space between open paren and contained expression",
                    expression.pos,
                )
            )
        if (
            expression.end_pos[0] == child.end_pos[0]
            and (expression.end_pos[1] - child.end_pos[1]) != 1
        ):
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "expected no space between close paren and contained expression",
                    child.end_pos,
                )
            )

    def visit_unary_op(self, unary_op):
        assert len(unary_op.children) == 2
        operator = unary_op.children[0]
        operand = unary_op.children[1]

        if operator.line != operand.line:
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "expected unary operator and operand to be on the same line",
                    unary_op.children[0].end_pos,
                )
            )

        spacing = operand.pos[1] - operator.end_pos[1]
        if spacing != 0:
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "expected no space between unary operator and operand",
                    unary_op.children[0].end_pos,
                )
            )

    def visit_function(self, function):
        """Function must be formatted like func(arg1, arg2, ...)"""
        last_child = function.children[0]
        for i, child in enumerate(function.children[1:]):
            if child.pos[0] != last_child.end_pos[0]:
                # ignore spacing if not on same line
                last_child = child
                continue

            spacing = child.pos[1] - last_child.end_pos[1]
            if i == 0 and spacing != 1:
                self.violations.append(
                    Violation(
                        Rule.EXPR_FORMAT,
                        "expected no space between opening paren of function and first"
                        " argument",
                        last_child.end_pos,
                    )
                )
            elif i % 2 == 0 and spacing != 1:
                self.violations.append(
                    Violation(
                        Rule.EXPR_FORMAT,
                        "expected 1 space between function arguments",
                        last_child.end_pos,
                    )
                )
            elif i % 2 == 1 and spacing != 0:
                self.violations.append(
                    Violation(
                        Rule.EXPR_FORMAT,
                        "expected no space between argument and following comma",
                        last_child.end_pos,
                    )
                )
            last_child = child

        if (function.end_pos[0] == last_child.end_pos[0]) and (
            function.end_pos[1] - last_child.end_pos[1] != 1
        ):
            self.violations.append(
                Violation(
                    Rule.EXPR_FORMAT,
                    "expected no space between final argument and closing paren of"
                    " function",
                    last_child.end_pos,
                )
            )


class BackslashNewlineChecker(Visitor):
    """Checks that backslash newline substitutions are spaced properly. Reports
    'backslash-spacing' violations."""

    def check(self, input, tree, config):
        self._excluded_ranges = []
        tree.accept(self, recurse=True)

        violations = []
        lines = input.split("\n")
        for min, max in self._excluded_ranges:
            for i in range(min, max):
                lines[i - 1] = None

        for i, line in enumerate(lines):
            if line is None:
                continue

            lineno = i + 1
            # TODO: whitespace after a backslash could be an error. It'll be
            # flagged as a trailing-whitespace violation, but maybe it's worth
            # flagging something more distinct?
            line = line.rstrip(" \t")
            if line.endswith("\\"):
                # count whitespace before \
                whitespace_count = 0
                for c in reversed(line[:-1]):
                    if c not in {" ", "\t"}:
                        break
                    whitespace_count += 1

                if whitespace_count == len(line) - 1:
                    # entire line consists of whitespace + \
                    # TODO: consider flagging violation here? this is probably
                    # not a necessary "\". could also be worth checking
                    # indentation of a lonely "\", if we allow them
                    continue
                if whitespace_count != 1 or line[-2] == "\t":
                    violations.append(
                        Violation(
                            Rule.BACKSLASH_SPACING,
                            "expected 1 space between line contents and backslash",
                            (lineno, len(line)),
                        )
                    )

        return violations

    def visit_braced_word(self, word):
        self._excluded_ranges.append((word.pos[0], word.end_pos[0]))

    def visit_quoted_word(self, word):
        self._excluded_ranges.append((word.pos[0], word.end_pos[0]))


class LineChecker:
    """Ensures lines aren't too long and do not include trailing whitespace.

    Reports 'line-length' and 'trailing-whitespace' violations.
    """

    # ref: https://github.com/eslint/eslint/blob/b29a16b22f234f6134475efb6c7be5ac946556ee/lib/rules/max-len.js#L101 # noqa: E501
    # ^ ironic lint waiver...
    URL_RE = re.compile(r"[^:/?#]:\/\/[^?#]")

    def check(self, input, _, config):
        violations = []
        for i, line in enumerate(input.split("\n")):
            if self.URL_RE.search(line) is not None:
                # ignore URLs
                continue

            lineno = i + 1
            if len(line) > config.style_line_length:
                pos = (lineno, config.style_line_length + 1)
                violations.append(
                    Violation(
                        Rule.LINE_LENGTH,
                        f"line length is {len(line)}, maximum allowed is"
                        f" {config.style_line_length}",
                        pos,
                    )
                )

            if line.endswith((" ", "\t")):
                pos = (lineno, len(line))
                violations.append(
                    Violation(
                        Rule.TRAILING_WHITESPACE, "line has trailing whitespace", pos
                    )
                )

        return violations


class RedefinedBuiltinChecker(Visitor):
    """Ensures names of built-in commands aren't reused by proc definitions.

    Reports 'redefined-builtin' violations.
    """

    def check(self, _, tree, config):
        self._violations = []

        plugins = [config.commands] if config.commands is not None else []
        builtin_commands = get_commands(plugins)
        self._commands = builtin_commands.keys()

        tree.accept(self, recurse=True)

        return self._violations

    def visit_command(self, command):
        if command.routine != "proc":
            return

        name = command.args[0].contents

        if name in self._commands:
            self._violations.append(
                Violation(
                    Rule.REDEFINED_BUILTIN,
                    f"redefinition of built-in command '{name}'",
                    command.pos,
                )
            )


class BlankLineChecker(Visitor):
    """Ensures that there aren't too many blank lines between commands/comments.

    Reports 'blank-lines' violations.
    """

    def check(self, _, tree, config):
        self._violations = []
        self._non_blank_ranges = []
        self._parent_is_block = False
        self._max_blank_lines = config.style_max_blank_lines
        tree.accept(self)
        return self._violations

    def visit_script(self, script):
        self._handle_block(script)

    def visit_comment(self, comment):
        self._handle_item(comment)

    def visit_command(self, command):
        self._handle_item(command)

    def visit_command_sub(self, command_sub):
        self._handle_item(command_sub)

    def visit_quoted_word(self, word):
        self._handle_item(word)

    def visit_compound_bare_word(self, word):
        self._handle_item(word)

    def visit_compound_var_sub(self, var_sub):
        self._handle_item(var_sub)

    def visit_arg_expansion(self, arg_expansion):
        self._handle_item(arg_expansion)

    def visit_list(self, list):
        self._handle_block(list)

    def _handle_block(self, block):
        # every time we visit a script/list, we record the extents of all
        # items within the first level of the block, and then check that
        # the gaps between them don't exceed max_blank_lines.

        # recording the full extent of an item  ensures that we don't flag
        # blank lines within e.g. a quoted multi-line string. we can then
        # recursively perform this check within any nested script arguments to
        # ensure we do check things like if statement bodies.

        # need to handle this case for switch commands, where we have a Script
        # node directly under a List node (which is a block)
        if self._parent_is_block:
            self._non_blank_ranges.append((block.pos[0], block.end_pos[0]))

        # we need to save and restore _non_blank_ranges to facilitate the recursion.
        prev_ranges = self._non_blank_ranges

        self._non_blank_ranges = [
            # (start_line, end_line)
        ]

        for child in block.children:
            self._parent_is_block = True
            child.accept(self)

        last_non_blank_line = block.pos[0]
        for start_line, end_line in self._non_blank_ranges:
            blank_lines = (start_line - last_non_blank_line) - 1

            if blank_lines > self._max_blank_lines:
                self._violations.append(
                    Violation(
                        Rule.BLANK_LINES,
                        f"found {blank_lines} blank lines,"
                        f" expected no more than {self._max_blank_lines}",
                        (last_non_blank_line + 1, 1),
                    )
                )
            last_non_blank_line = end_line

        blank_lines = (block.end_pos[0] - last_non_blank_line) - 1
        if blank_lines > self._max_blank_lines:
            self._violations.append(
                Violation(
                    Rule.BLANK_LINES,
                    f"found {blank_lines} blank lines,"
                    f" expected no more than {self._max_blank_lines}",
                    (last_non_blank_line + 1, 1),
                )
            )

        self._non_blank_ranges = prev_ranges

    def _handle_item(self, item):
        if self._parent_is_block:
            self._non_blank_ranges.append((item.pos[0], item.end_pos[0]))
        for child in item.children:
            self._parent_is_block = False
            child.accept(self)


class SpacesInBracesChecker(Visitor):
    def check(self, _, tree, config):
        self._violations = []
        self._spaces_in_braces = config.style_spaces_in_braces
        tree.accept(self, recurse=True)
        return self._violations

    def visit_script(self, script):
        if not script.braced:
            # We tag whether a script is braced using this member. It's a bit of
            # a hack - it would probably be better to have a BracedScript
            # analagous to BracedExpression, but that change is more invasive.
            #
            # We can distinguish between a braced and bare script using
            # positions, but this extra info is important so we don't check
            # quoted scripts.
            return

        return self._check_braced_arg(script)

    def visit_braced_expression(self, expression):
        return self._check_braced_arg(expression)

    def _check_braced_arg(self, node):
        if len(node.children) == 0:
            # TODO: consider enforcing {} vs { }
            return

        if self._spaces_in_braces:
            expected_spacing = 2
            message = "expected 1 space between contents and enclosing braces"
        else:
            expected_spacing = 1
            message = "expected no space between contents and enclosing braces"

        # check violation at beginning
        first = node.children[0]
        if (
            first.pos[0] == node.pos[0]
            and first.pos[1] - node.pos[1] != expected_spacing
        ):
            self._violations.append(
                Violation(
                    Rule.SPACES_IN_BRACES,
                    message,
                    node.pos,
                )
            )
            return

        # check violation at end
        last = node.children[-1]
        if (
            node.end_pos[0] == last.end_pos[0]
            and node.end_pos[1] - last.end_pos[1] != expected_spacing
        ):
            self._violations.append(
                Violation(
                    Rule.SPACES_IN_BRACES,
                    message,
                    last.end_pos,
                )
            )


class UnbracedExprChecker(Visitor):
    def check(self, _, tree, __):
        self._violations = []
        tree.accept(self, recurse=True)
        return self._violations

    def visit_command(self, command):
        if command.routine != "expr":
            return

        if len(command.args) == 1 and isinstance(command.args[0], BracedExpression):
            return

        for child in command.args:
            if child.contents is None:
                self._violations.append(
                    Violation(
                        Rule.UNBRACED_EXPR,
                        "expression with substitutions should be enclosed by braces",
                        command.args[0].pos,
                    )
                )
                return


def get_checkers():
    return (
        IndentLevelChecker(),
        SpacingChecker(),
        LineChecker(),
        RedefinedBuiltinChecker(),
        BlankLineChecker(),
        BackslashNewlineChecker(),
        SpacesInBracesChecker(),
        UnbracedExprChecker(),
    )
