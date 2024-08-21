import dataclasses
from typing import List, Tuple, Union
import sys

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
from tclint.parser import Parser
from tclint.syntax_tree import List as ListNode


@dataclasses.dataclass
class LiteralBlock:
    block: List[str]
    pos: Tuple[int, int]
    end_pos: Tuple[int, int]


@dataclasses.dataclass
class FormatterOpts:
    indent: str
    spaces_in_braces: bool
    max_blank_lines: int
    indent_namespace_eval: bool


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
        if lines == [""]:
            return ["{" + spaces_in_braces + "}"]

        braced_lines = lines[:]
        braced_lines[0] = "{" + spaces_in_braces + lines[0]
        braced_lines[-1] += spaces_in_braces + "}"
        return braced_lines

    def format(self, *nodes: Union[Node, LiteralBlock]) -> List[str]:
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
            elif isinstance(node, LiteralBlock):
                formatted += node.block
            else:
                assert False, f"unrecognized node: {type(node)}"

        return formatted

    def format_top(self, script: str, parser: Parser) -> str:
        tree = parser.parse(script)
        self.script = script.split("\n")
        return "\n".join(self.format_script_contents(tree)) + "\n"

    def format_script_contents(self, script: Union[Script, CommandSub]) -> List[str]:
        to_format = []
        skip_formatting_start = None
        for child in script.children:
            if skip_formatting_start is None:
                to_format.append(child)

            if isinstance(child, Comment):
                if child.value.strip() == "tclfmt-disable":
                    if skip_formatting_start is not None:
                        print(
                            "Warning: encountered 'tclint-disable' while formatting is"
                            " already disabled, ignoring...",
                            file=sys.stderr,
                        )
                    else:
                        skip_formatting_start = child.pos[0]
                elif child.value.strip() == "tclfmt-enable":
                    if skip_formatting_start is None:
                        print(
                            "Warning: encountered 'tclint-enable' while formatting is"
                            " already disabled, ignoring...",
                            file=sys.stderr,
                        )
                    else:
                        skip_formatting_end = child.pos[0]
                        block = self.script[skip_formatting_start:skip_formatting_end]
                        to_format.append(
                            LiteralBlock(
                                block,
                                pos=(skip_formatting_start + 1, 1),
                                end_pos=(skip_formatting_end, 1),
                            )
                        )
                        skip_formatting_start = None

        if skip_formatting_start is not None:
            print("Warning: missing 'tclint-enable'", file=sys.stderr)
            to_format.append(
                LiteralBlock(
                    self.script[skip_formatting_start:],
                    pos=(skip_formatting_start + 1, 1),
                    end_pos=script.end_pos,
                )
            )

        formatted = [""]
        last_line = None
        for child in to_format:
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

    def format_script(self, script: Script, should_indent=True) -> List[str]:
        lines = self.format_script_contents(script)
        if script.pos[0] == script.end_pos[0]:
            return self._brace(lines)

        # Usually, we enforce that multi-line scripts start on a new line after the open
        # brace. However, if a comment was originally on the same line as the open brace
        # we preserve it, since it's probably meant to be associated with this line
        # (e.g. a tclint-disable-line).
        open_brace = "{"
        if (
            len(script.children) > 0
            and isinstance(script.children[0], Comment)
            and script.pos[0] == script.children[0].pos[0]
        ):
            open_brace += " " + lines[0]
            lines = lines[1:]

        if should_indent:
            return [open_brace] + self._indent(lines, self.opts.indent) + ["}"]
        else:
            return [open_brace] + lines + ["}"]

    def format_command(self, command) -> List[str]:
        # TODO: enforce in type
        assert len(command.children) > 0

        is_namespace_eval = (
            command.routine == "namespace"
            and len(command.args) > 0
            and command.args[0].contents == "eval"
        )
        should_indent = not is_namespace_eval or self.opts.indent_namespace_eval

        hanging_indent = False
        formatted = self.format(command.children[0])
        last_line = command.children[0].end_pos[0]
        for child in command.children[1:]:
            if isinstance(child, Script):
                child_lines = self.format_script(child, should_indent=should_indent)
            else:
                child_lines = self.format(child)

            if last_line == child.pos[0]:
                formatted[-1] += " "
                formatted[-1] += child_lines[0]
            else:
                formatted[-1] += " \\"
                formatted.append(self.opts.indent + child_lines[0])
                hanging_indent = True

            if hanging_indent:
                formatted.extend(self._indent(child_lines[1:], self.opts.indent))
            else:
                formatted.extend(child_lines[1:])

            last_line = child.end_pos[0]

        return formatted

    def format_comment(self, comment: Comment) -> List[str]:
        return [f"#{comment.value}"]

    def format_command_sub(self, command_sub):
        if len(command_sub.children) == 0:
            return ["[]"]

        formatted = []
        contents = self.format_script_contents(command_sub)
        if len(command_sub.children) > 1 and len(contents) > 1:
            formatted.append("[")
            formatted.extend(self._indent(contents, self.opts.indent))
            formatted.append("]")
        else:
            formatted.append("[" + contents[0])
            formatted.extend(contents[1:])
            formatted[-1] += "]"

        return formatted

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
            formatted[-1] += child_lines[0]
            formatted.extend(child_lines[1:])

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
            # We just concatenate everything as is, since changes in whitespace are
            # semantically meaningful in this context. Any newlines are captured by
            # BareWords.
            formatted[-1] += "("
            for child in varsub.children:
                child_lines = self.format(child)
                formatted[-1] += child_lines[0]
                formatted.extend(child_lines[1:])
            formatted[-1] += ")"

        return formatted

    def format_arg_expansion(self, arg_expansion) -> List[str]:
        # TODO: enforce in type?
        assert len(arg_expansion.children) == 1
        lines = self.format(arg_expansion.children[0])
        lines[0] = "{*}" + lines[0]

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

        # Trick: we know there are quotes around the expression if the start of the
        # expression is a different column than its first child.
        quoted = expr.pos[1] != expr.children[0].pos[1]
        if quoted:
            formatted[0] = '"' + formatted[0]
            formatted[-1] += '"'

        return formatted

    def format_braced_expression(self, expr) -> List[str]:
        formatted = [""]
        for child in expr.children:
            lines = self.format(child)
            formatted[-1] += lines[0]
            formatted.extend(lines[1:])

        if expr.pos[0] == expr.end_pos[0]:
            return self._brace(formatted)

        return ["{"] + self._indent(formatted, self.opts.indent) + ["}"]

    def format_paren_expression(self, expr) -> List[str]:
        # TODO: enforce in type?
        assert len(expr.children) == 1
        body = expr.children[0]

        formatted = ["("]
        lines = self.format(body)
        if expr.pos[0] != body.pos[0]:
            formatted.extend(lines)
        else:
            formatted[-1] += lines[0]
            formatted.extend(lines[1:])

        formatted = formatted[0:1] + self._indent(formatted[1:], self.opts.indent)

        if expr.end_pos[0] != body.end_pos[0]:
            formatted.append(")")
        else:
            formatted[-1] += ")"

        return formatted

    def format_unary_op(self, expr):
        # TODO: enforce in type?
        assert len(expr.children) == 2

        op = self.format(expr.children[0])
        assert len(op) == 1

        lines = self.format(expr.children[1])
        lines[0] = op[0] + lines[0]
        return lines

    def _format_op(self, expr) -> List[str]:
        nodes = expr.children
        formatted = self.format(nodes[0])

        last = nodes[0]
        for next in nodes[1:]:
            lines = self.format(next)
            if last.end_pos[0] != next.pos[0]:
                formatted.extend(lines)
            else:
                formatted[-1] += " "
                formatted[-1] += lines[0]
                formatted.extend(lines[1:])
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

        last = function.children[0]
        for i, child in enumerate(function.children[1:]):
            if child == BareWord(","):
                continue
            if i > 0:
                formatted[-1] += ","
            lines = self.format(child)
            if last.end_pos[0] != child.pos[0]:
                formatted.extend(lines)
            else:
                if i > 0:
                    formatted[-1] += " "
                formatted[-1] += lines[0]
                formatted.extend(lines[1:])
            last = child

        # indent any continuation lines, but we leave the closing paren dedented
        formatted = formatted[0:1] + self._indent(formatted[1:], self.opts.indent)

        if last.end_pos[0] != function.end_pos[0]:
            formatted.append(")")
        else:
            formatted[-1] += ")"

        return formatted
