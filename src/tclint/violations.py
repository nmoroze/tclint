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

    def __str__(self):
        return self.value


ALL_RULES = [rule for rule in Rule]


class Violation:
    def __init__(self, id: Rule, message: str, pos: Tuple[int, int]):
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
