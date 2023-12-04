from typing import Tuple


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


violation_types = [
    "indent",
    "spacing",
    "line-length",
    "trailing-whitespace",
    "command-args",
]

IndentViolation = Violation.create("indent")
SpacingViolation = Violation.create("spacing")
LineLengthViolation = Violation.create("line-length")
TrailingWhiteSpaceViolation = Violation.create("trailing-whitespace")
# used by parser. TODO: should this be separated per command?
CommandArgViolation = Violation.create("command-args")
