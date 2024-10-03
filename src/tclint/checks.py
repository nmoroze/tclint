import re

from tclint.commands import get_commands
from tclint.violations import Rule, Violation

from tclint.syntax_tree import (
    Visitor,
    BracedExpression,
    Expression,
    BracedWord,
    QuotedWord,
    CommandSub,
)


class LineLengthChecker:
    """Ensures lines aren't too long.

    Reports 'line-length' violations.
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
                start = (lineno, 1)
                end = (lineno, len(line) + 1)
                violations.append(
                    Violation(
                        Rule.LINE_LENGTH,
                        f"line length is {len(line)}, maximum allowed is"
                        f" {config.style_line_length}",
                        start,
                        end,
                    )
                )

        return violations


class TrailingWhitespaceChecker:
    """Ensures lines don't include trailing whitespace.

    Reports 'trailing-whitespace' violations.
    """

    def check(self, input, _, config):
        violations = []
        for i, line in enumerate(input.split("\n")):
            lineno = i + 1

            WHITESPACE = (" ", "\t")
            if line.endswith(WHITESPACE):
                start_col = len(line.rstrip("".join(WHITESPACE)))
                start = (lineno, start_col + 1)
                end = (lineno, len(line) + 1)
                violations.append(
                    Violation(
                        Rule.TRAILING_WHITESPACE,
                        "line has trailing whitespace",
                        start,
                        end,
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

        if len(command.args) == 0:
            # This is a syntax error, but should already be caught as a command-args
            # error by the parser's `proc` command handling.
            return

        name = command.args[0].contents

        if name in self._commands:
            self._violations.append(
                Violation(
                    Rule.REDEFINED_BUILTIN,
                    f"redefinition of built-in command '{name}'",
                    command.pos,
                    command.args[1].end_pos,
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

        if len(command.args) == 0:
            # This is a syntax error, but should already be caught as a command-args
            # error by the parser's `expr` command handling.
            return

        if len(command.args) == 1 and isinstance(
            command.args[0], (BracedExpression, Expression)
        ):
            return

        # If we got here, tclint had trouble parsing the expression due to one of the
        # two following cases.

        for child in command.args:
            if child.contents is None:
                self._violations.append(
                    Violation(
                        Rule.UNBRACED_EXPR,
                        "expression with substitutions should be enclosed by braces",
                        command.args[0].pos,
                        command.args[-1].end_pos,
                    )
                )
                return

        for child in command.args:
            if isinstance(child, (BracedWord, QuotedWord)):
                self._violations.append(
                    Violation(
                        Rule.UNBRACED_EXPR,
                        "expression containing braced or quoted words should be"
                        " enclosed by braces",
                        command.args[0].pos,
                        command.args[-1].end_pos,
                    )
                )
                return

        # If we reach here, there's probably a bug in expr parsing logic.
        assert False, (
            "Children of expr node were different than expected, please file a bug"
            " report"
        )


class RedundantExprChecker(Visitor):
    def check(self, _, tree, __):
        self._violations = []
        tree.accept(self, recurse=True)
        return self._violations

    def _check_operand(self, operand):
        if not isinstance(operand, CommandSub) or len(operand.children) != 1:
            return

        command = operand.children[0]
        if command.routine == "expr":
            self._violations.append(
                Violation(
                    Rule.REDUNDANT_EXPR,
                    "unnecessary command substitution within expression",
                    operand.pos,
                    operand.end_pos,
                )
            )

    def visit_braced_expression(self, expression):
        if len(expression.children) == 1:
            self._check_operand(expression.children[0])

    def visit_expression(self, expression):
        if len(expression.children) == 1:
            self._check_operand(expression.children[0])

    def visit_unary_op(self, expr):
        self._check_operand(expr.children[1])

    def visit_binary_op(self, expr):
        self._check_operand(expr.children[0])
        self._check_operand(expr.children[2])

    def visit_ternary_op(self, expr):
        self._check_operand(expr.children[0])
        self._check_operand(expr.children[2])
        self._check_operand(expr.children[4])

    def visit_function(self, function):
        for arg in function.children[1:]:
            self._check_operand(arg)


def get_checkers():
    checkers = (
        RedefinedBuiltinChecker(),
        UnbracedExprChecker(),
        RedundantExprChecker(),
        LineLengthChecker(),
        TrailingWhitespaceChecker(),
    )

    return checkers
