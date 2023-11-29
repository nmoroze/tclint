from tclint.syntax_tree import Node


def pytest_assertrepr_compare(op, left, right):
    if isinstance(left, Node) and isinstance(right, Node) and op == "==":
        return ["Syntax trees not equal", *left.diff(right)]
