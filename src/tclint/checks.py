import re
from typing import Tuple

from tclint.syntax_tree import Visitor, Script, List


class Violation:
    def __init__(self, id: str, message: str, pos: Tuple[int, int]):
        self.id = id
        self.message = message
        self.pos = pos

    def __lt__(self, other):
        return self.pos < other.pos

    def __str__(self):
        line, col = self.pos
        return f"{line}:{col}: {self.message} [{self.id}]"

    @classmethod
    def create(cls, id):
        def func(message: str, pos: Tuple[int, int]):
            return cls(id, message, pos)

        return func


IndentViolation = Violation.create("indent")
SpacingViolation = Violation.create("spacing")
LineLengthViolation = Violation.create("line-length")
TrailingWhiteSpaceViolation = Violation.create("trailing-whitespace")
# used by parser. TODO: should this be separated per command?
CommandArgViolation = Violation.create("command-args")


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
        # first have visitor calculate expected indent on each line
        tree.accept(self, recurse=False)

        # then iterate line-by-line to verify that actual indentation matches
        violations = []
        for lineno, line in enumerate(input.split("\n")):
            # 1-indexed
            lineno += 1

            if lineno not in self.expected_levels:
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
                    IndentViolation(
                        f"expected indent of {expected_str}, got {actual_str}",
                        pos,
                    )
                )

        return violations

    def visit_script(self, script):
        self._visit_script(script)

    def visit_list(self, list):
        # List works like Script for indent checking purposes
        self._visit_script(list)

    def _visit_script(self, script):
        self.level += 1
        for child in script.children:
            child.accept(self)
        self.level -= 1

        # check indentation of closing token of script
        if script.end_pos:
            end_line, _ = script.end_pos
            if end_line not in self.expected_levels:
                self.expected_levels[end_line] = self.level

    def visit_command(self, command):
        assert len(command.children) > 0

        if command.line in self.expected_levels:
            # already visited something on this line
            # TODO: do we want to return here? do we still wanna check continuation?
            return

        self.expected_levels[command.line] = self.level

        for child in command.children:
            # continuations of command must be indented. If the node is a list
            # or script however, the indentation only applies to contents of that node
            # (handled by the relevant visitors)
            if not isinstance(child, (Script, List)):
                self.level += 1

            child.accept(self)

            if not isinstance(child, (Script, List)):
                self.level -= 1

    def visit_comment(self, comment):
        self._set_level(comment)

    def visit_command_sub(self, command_sub):
        self._set_level(command_sub)

    def visit_bare_word(self, word):
        self._set_level(word)

    def visit_braced_word(self, word):
        self._set_level(word)

    def visit_quoted_word(self, word):
        self._set_level(word)

    def visit_compound_bare_word(self, word):
        self._set_level(word)

    def visit_var_sub(self, var_sub):
        self._set_level(var_sub)

    def visit_arg_expansion(self, arg_expansion):
        self._set_level(arg_expansion)

    def _set_level(self, node):
        if node.line in self.expected_levels:
            return

        self.expected_levels[node.line] = self.level


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
        self.aligned_set = config.style_aligned_set

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
                    SpacingViolation(
                        f"expected 1 space between words, got {spacing}",
                        last_word.end_pos,
                    )
                )
            last_word = word

    def _check_set_spacing(self):
        for group in self.set_groups:
            furthest_value_start = 0
            for i, cmd in enumerate(group):
                value_start = cmd.args[1].pos[1]
                if value_start > furthest_value_start:
                    furthest_value_start = value_start

            violations = []
            all_aligned = True
            for i, cmd in enumerate(group):
                if cmd.args[1].pos[1] != furthest_value_start:
                    all_aligned = False

                spacing = cmd.args[1].pos[1] - cmd.args[0].end_pos[1]
                if spacing != 1:
                    violations.append(
                        SpacingViolation(
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
                    LineLengthViolation(
                        f"line length is {len(line)}, maximum allowed is"
                        f" {config.style_line_length}",
                        pos,
                    )
                )

            if line.endswith((" ", "\t")):
                pos = (lineno, len(line))
                violations.append(
                    TrailingWhiteSpaceViolation("line has trailing whitespace", pos)
                )

        return violations
