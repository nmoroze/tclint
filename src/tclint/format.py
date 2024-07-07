import dataclasses
from typing import List

from tclint.syntax_tree import (
    Node,
    Script,
    Command,
    Comment,
    CommandSub,
    BareWord,
    QuotedWord,
    BracedWord,
    CompoundBareWord,
    VarSub,
    ArgExpansion,
    Expression,
    BracedExpression,
    ParenExpression,
    UnaryOp,
    BinaryOp,
    TernaryOp,
    Function,
)
from tclint.syntax_tree import List as ListNode


@dataclasses.dataclass
class FormatterOpts:
    indent: str
    spaces_in_braces: bool
    max_blank_lines: int


class Formatter:
    def __init__(self, opts: FormatterOpts):
        self.opts = opts

    def _indent(self, lines: List[str], indent: str) -> List[str]:
        indented = []
        for line in lines:
            if line == "":
                indented.append("")
            else:
                indented.append(indent + line)

        return indented

    def _brace(self, lines: List[str]) -> List[str]:
        spaces_in_braces = " " if self.opts.spaces_in_braces else ""
        braced_lines = lines[:]
        braced_lines[0] = "{" + spaces_in_braces + lines[0]
        braced_lines[-1] += spaces_in_braces + "}"
        return braced_lines

    def format(self, *nodes: Node) -> List[str]:
        formatted = []
        for node in nodes:
            if isinstance(node, Script):
                formatted += self.format_script(node)
            elif isinstance(node, Command):
                formatted += self.format_command(node)
            elif isinstance(node, Comment):
                formatted += self.format_comment(node)
            elif isinstance(node, CommandSub):
                formatted += self.format_command_sub(node)
            elif isinstance(node, BareWord):
                formatted += self.format_bare_word(node)
            elif isinstance(node, QuotedWord):
                formatted += self.format_quoted_word(node)
            elif isinstance(node, BracedWord):
                formatted += self.format_braced_word(node)
            elif isinstance(node, CompoundBareWord):
                formatted += self.format_compound_bare_word(node)
            elif isinstance(node, VarSub):
                formatted += self.format_var_sub(node)
            elif isinstance(node, ArgExpansion):
                formatted += self.format_arg_expansion(node)
            elif isinstance(node, ListNode):
                formatted += self.format_list(node)
            elif isinstance(node, Expression):
                formatted += self.format_expression(node)
            elif isinstance(node, BracedExpression):
                formatted += self.format_braced_expression(node)
            elif isinstance(node, ParenExpression):
                formatted += self.format_paren_expression(node)
            elif isinstance(node, UnaryOp):
                formatted += self.format_unary_op(node)
            elif isinstance(node, BinaryOp):
                formatted += self.format_binary_op(node)
            elif isinstance(node, TernaryOp):
                formatted += self.format_ternary_op(node)
            elif isinstance(node, Function):
                formatted += self.format_function(node)
            else:
                assert False, f"unrecognized node: {type(node)}"

        return formatted

    def format_top(self, script: Script) -> str:
        return "\n".join(self.format_script_contents(script)) + "\n"

    def format_script_contents(self, script: Script) -> List[str]:
        formatted = [""]
        last_line = None
        for child in script.children:
            if last_line is not None:
                if last_line == child.pos[0]:
                    if isinstance(child, Comment):
                        formatted[-1] += " ;"
                    else:
                        formatted[-1] += "; "
                else:
                    newlines = child.pos[0] - last_line
                    newlines = min(newlines, self.opts.max_blank_lines + 1)
                    formatted.extend([""] * newlines)
            last_line = child.end_pos[0]

            lines = self.format(child)
            formatted[-1] += lines[0]
            formatted.extend(lines[1:])

        return formatted

    def format_script(self, script: Script) -> List[str]:
        lines = self.format_script_contents(script)
        if script.pos[0] == script.end_pos[0]:
            return self._brace(lines)

        return ["{"] + self._indent(lines, self.opts.indent) + ["}"]

    def format_command(self, command) -> List[str]:
        # TODO: enforce in type
        assert len(command.children) > 0

        formatted = self.format(command.children[0])
        last_line = command.children[0].end_pos[0]
        for child in command.children[1:]:
            child_lines = self.format(child)
            if last_line == child.pos[0]:
                formatted[-1] += " "
                indent = " " * len(formatted[-1])
                formatted[-1] += child_lines[0]
                if isinstance(child, (Script, ListNode)):
                    formatted.extend(child_lines[1:])
                else:
                    formatted.extend(self._indent(child_lines[1:], indent))
            else:
                formatted[-1] += " \\"
                formatted.extend(self._indent(child_lines, self.opts.indent))

            last_line = child.end_pos[0]

        return formatted

    def format_comment(self, comment: Comment) -> List[str]:
        return [f"#{comment.value}"]

    def format_command_sub(self, command_sub):
        if len(command_sub.children) == 0:
            return ["[]"]

        # TODO: enforce in type?
        assert len(command_sub.children) == 1
        assert isinstance(command_sub.children[0], Command)

        child_lines = self.format(command_sub.children[0])
        lines = ["[" + child_lines[0]]
        # Add extra space to account for [
        lines.extend(self._indent(child_lines[1:], " "))
        lines[-1] += "]"

        return lines

    def format_bare_word(self, word) -> List[str]:
        # Property enforced by parser
        assert word.contents is not None
        return [word.contents]

    def format_quoted_word(self, word) -> List[str]:
        if word.contents is not None:
            return [f'"{word.contents}"']

        formatted = ""
        for child in word.children:
            formatted += "\n".join(self.format(child))

        return [f'"{formatted}"']

    def format_braced_word(self, word) -> List[str]:
        assert word.contents is not None
        return [f"{{{word.contents}}}"]

    def format_compound_bare_word(self, word) -> List[str]:
        formatted = [""]
        for child in word.children:
            child_lines = self.format(child)
            indent = " " * len(formatted[-1])
            formatted[-1] += child_lines[0]
            formatted.extend(self._indent(child_lines[1:], indent))

        return formatted

    def format_var_sub(self, varsub) -> List[str]:
        # We might be able to make the formatter infer whether braces are required, and
        # remove them from the syntax tree. For now it's easier to just mimic the
        # original format.
        if varsub.braced:
            formatted = [f"${{{varsub.value}}}"]
        else:
            formatted = [f"${varsub.value}"]

        if varsub.children:
            formatted[-1] += "("
            for child in varsub.children:
                indent = " " * len(formatted[-1])
                child_lines = self.format(child)
                formatted[-1] += child_lines[0]
                formatted.extend(self._indent(child_lines[1:], indent))
            formatted[-1] += ")"

        return formatted

    def format_arg_expansion(self, arg_expansion) -> List[str]:
        # TODO: enforce in type?
        assert len(arg_expansion.children) == 1
        lines = self.format(arg_expansion.children[0])
        lines[0] = "{*}" + lines[0]
        indent = " " * len("{*}")
        lines[1:] = self._indent(lines[1:], indent)

        return lines

    def format_list(self, list_node) -> List[str]:
        # Similar to Script, but the contents are a bit more straightforward.
        contents = [""]
        last_line = None
        for child in list_node.children:
            if last_line is not None:
                if last_line == child.pos[0]:
                    contents[-1] += " "
                else:
                    newlines = child.pos[0] - last_line
                    newlines = min(newlines, 3)
                    contents.extend([""] * newlines)

            lines = self.format(child)
            contents[-1] += lines[0]
            contents.extend(lines[1:])

            last_line = child.end_pos[0]

        if list_node.pos[0] == list_node.end_pos[0]:
            return self._brace(contents)

        return ["{"] + self._indent(contents, self.opts.indent) + ["}"]

    def format_expression(self, expr) -> List[str]:
        # TODO: add \ where needed
        formatted = [""]
        for child in expr.children:
            lines = self.format(child)
            formatted[-1] += lines[0]
            formatted.extend(lines[1:])

        return formatted

    def format_braced_expression(self, expr) -> List[str]:
        formatted = [""]
        indent = "  " if self.opts.spaces_in_braces else " "
        for child in expr.children:
            lines = self.format(child)
            formatted[-1] += lines[0]
            formatted.extend(self._indent(lines[1:], indent))

        return self._brace(formatted)

    def format_paren_expression(self, expr) -> List[str]:
        formatted = ["("]
        for child in expr.children:
            lines = self.format(child)
            formatted[-1] += lines[0]
            formatted.extend(self._indent(lines[1:], " "))
        formatted[-1] += ")"

        return formatted

    def format_unary_op(self, expr):
        # TODO: enforce in type?
        assert len(expr.children) == 2

        op = self.format(expr.children[0])
        assert len(op) == 1

        lines = self.format(expr.children[1])
        lines[0] = op[0] + lines[0]
        lines[1:] = self._indent(lines[1:], " " * len(op[0]))
        return lines

    def _flatten_op(self, expr) -> List[Node]:
        """Flatening nested BinaryOps and TernaryOps lets us add indents for alignment
        that affect multi-line ParenExpressions, Functions, and CommandSubs while
        ensuring that multi-line BinaryOps/TernaryOps are aligned with the opening of
        the expression itself."""
        nodes = []
        for node in expr.children:
            if isinstance(node, (BinaryOp, TernaryOp)):
                nodes.extend(self._flatten_op(node))
            else:
                nodes.append(node)
        return nodes

    def _format_op(self, expr) -> List[str]:
        nodes = self._flatten_op(expr)
        formatted = self.format(nodes[0])

        last = nodes[0]
        for next in nodes[1:]:
            lines = self.format(next)
            if last.end_pos[0] != next.pos[0]:
                formatted.extend(lines)
            else:
                formatted[-1] += " "
                indent = " " * len(formatted[-1])
                formatted[-1] += lines[0]
                formatted.extend(self._indent(lines[1:], indent))
            last = next

        return formatted

    def format_binary_op(self, expr) -> List[str]:
        # TODO: enforce in type?
        assert len(expr.children) == 3
        return self._format_op(expr)

    def format_ternary_op(self, expr) -> List[str]:
        # TODO: enforce in type?
        assert len(expr.children) == 5
        return self._format_op(expr)

    def format_function(self, function):
        # TODO: enforce in type?
        assert len(function.children) >= 1

        name = self.format(function.children[0])
        assert len(name) == 1
        name = name[0]

        formatted = [f"{name}("]
        indent = " " * len(formatted[-1])

        last = function.children[0]
        for i, child in enumerate(function.children[1:]):
            if child == BareWord(","):
                continue
            if i > 0:
                formatted[-1] += ","
            lines = self.format(child)
            if last.end_pos[0] != child.pos[0]:
                formatted.extend(self._indent(lines, indent))
            else:
                if i > 0:
                    formatted[-1] += " "
                formatted[-1] += lines[0]
                formatted.extend(lines[1:])
        formatted[-1] += ")"

        return formatted
