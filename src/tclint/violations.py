from enum import Enum
from typing import Tuple


class Rule(Enum):
    """This enum serves a few purposes:

    1) define symbols for rule IDs to be used in code
    2) map these symbols to names in the UI
    3) collect all rule IDs/provide validation for IDs
    """

    LINE_LENGTH = "line-length"
    TRAILING_WHITESPACE = "trailing-whitespace"
    COMMAND_ARGS = "command-args"
    REDEFINED_BUILTIN = "redefined-builtin"
    UNBRACED_EXPR = "unbraced-expr"
    REDUNDANT_EXPR = "redundant-expr"

    def __str__(self):
        return self.value


ALL_RULES = [rule for rule in Rule]


class Violation:
    def __init__(
        self, id: Rule, message: str, start: Tuple[int, int], end: Tuple[int, int]
    ):
        self.id = id
        self.message = message
        self.start = start
        self.end = end

    def __lt__(self, other):
        return self.start < other.start

    def str(self):
        line, col = self.start
        rule = str(self.id)

        return f"{line}:{col}: {self.message} [{rule}]"

    @classmethod
    def create(cls, id):
        def func(message: str, start: Tuple[int, int], end: Tuple[int, int]):
            return cls(id, message, start, end)

        return func
