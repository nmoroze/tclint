from enum import Enum
from typing import Tuple


class Rule(Enum):
    """This enum serves a few purposes:

    1) define symbols for rule IDs to be used in code
    2) map these symbols to names in the UI
    3) collect all rule IDs/provide validation for IDs
    """

    INDENT = "indent"
    SPACING = "spacing"
    LINE_LENGTH = "line-length"
    TRAILING_WHITESPACE = "trailing-whitespace"
    COMMAND_ARGS = "command-args"
    REDEFINED_BUILTIN = "redefined-builtin"
    BLANK_LINES = "blank-lines"
    BACKSLASH_SPACING = "backslash-spacing"
    EXPR_FORMAT = "expr-format"
    SPACES_IN_BRACES = "spaces-in-braces"
    UNBRACED_EXPR = "unbraced-expr"

    def __str__(self):
        return self.value


ALL_RULES = [rule for rule in Rule]


class Category(Enum):
    FUNC = "func"
    STYLE = "style"

    def __str__(self):
        return self.value


_CATEGORY_MAP = {
    Rule.INDENT: Category.STYLE,
    Rule.SPACING: Category.STYLE,
    Rule.LINE_LENGTH: Category.STYLE,
    Rule.TRAILING_WHITESPACE: Category.STYLE,
    Rule.BLANK_LINES: Category.STYLE,
    Rule.BACKSLASH_SPACING: Category.STYLE,
    Rule.EXPR_FORMAT: Category.STYLE,
    Rule.SPACES_IN_BRACES: Category.STYLE,
    Rule.REDEFINED_BUILTIN: Category.FUNC,
    Rule.COMMAND_ARGS: Category.FUNC,
    Rule.UNBRACED_EXPR: Category.FUNC,
}


class Violation:
    def __init__(self, id: Rule, message: str, pos: Tuple[int, int]):
        self.id = id
        self.message = message
        self.pos = pos

    def __lt__(self, other):
        return self.pos < other.pos

    def str(self, show_category=False):
        line, col = self.pos
        rule = str(self.id)
        if show_category:
            category = str(_CATEGORY_MAP.get(self.id, ""))
            rule = ":".join([category, rule])

        return f"{line}:{col}: {self.message} [{rule}]"

    @classmethod
    def create(cls, id):
        def func(message: str, pos: Tuple[int, int]):
            return cls(id, message, pos)

        return func
