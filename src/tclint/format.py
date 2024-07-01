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

# TODO: replace with real config
_STYLE_LINE_LENGTH = 80
_STYLE_INDENT = "  "
_STYLE_SPACES_IN_BRACES = " "


class Formatter:
    def __init__(self):
        pass

    def format(self, *nodes: Node) -> str:
        formatted = ""
        for node in nodes:
            if isinstance(node, Script):
                formatted += self.format_script(node)
            elif isinstance(node, Command):
                formatted += self.format_command(node)
            elif isinstance(node, Comment):
                formatted += self.format_comment(node)
            elif isinstance(node, CommandSub):
                formatted += self.format_command(node)
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
        formatted = ""
        last_line = None

        for child in script.children:
            if last_line is not None:
                # We preserve line breaks in the input tree to an extent, but allow at
                # most two consecutive blank lines. This eliminates `blank-lines`
                # violations. Spacing between commands/comments on the same line is
                # normalized, although this isn't checked by tclint.
                if last_line == child.pos[0]:
                    if isinstance(child, Comment):
                        formatted += "  ;"
                    else:
                        formatted += "; "
                else:
                    newlines = child.pos[0] - last_line
                    newlines = min(newlines, 3)
                    formatted += "\n" * newlines

            formatted += self.format(child)
            last_line = child.end_pos[0]

        return formatted

    def format_script(self, script) -> str:
        script_contents = self.format_top(script)
        if script.pos[0] == script.end_pos[0]:
            return _STYLE_SPACES_IN_BRACES.join(["{", script_contents, "}"])

        return (
            "{\n"
            + _STYLE_INDENT
            + script_contents.replace("\n", "\n" + _STYLE_INDENT)
            + "\n}"
        )

    def format_command(self, command) -> str:
        words = []
        for child in command.children:
            words.append(self.format(child))

        formatted = " ".join(words)

        # TODO this doesn't work, we must know the current indentation
        # TODO: handle grouping switches w/ args
        # if len(formatted) > _STYLE_LINE_LENGTH:
        #     formatted = (" \\\n" + _STYLE_INDENT).join(words)

        return formatted

    def format_comment(self, comment: Comment) -> str:
        return f"#{comment.value}"

    def visit_command_sub(self, command_sub):
        # TODO: enforce in type?
        assert len(command_sub.children) == 1
        assert isinstance(command_sub.children[0], Command)

        return f"[{self.format(command_sub.children[0])}]"

    def format_bare_word(self, word) -> str:
        assert word.contents is not None
        return word.contents

    def format_quoted_word(self, word) -> str:
        if word.contents is not None:
            return f'"{word.contents}"'

        formatted = ""
        for child in word.children:
            formatted += self.format(child)

        return f'"{formatted}"'

    def format_braced_word(self, word) -> str:
        assert word.contents is not None
        return f"{{{word.contents}}}"

    def format_compound_bare_word(self, word) -> str:
        formatted = ""
        for child in word.children:
            formatted += self.format(child)

        return formatted

    def format_var_sub(self, varsub) -> str:
        formatted = f"${varsub.value}"
        if varsub.children:
            formatted += "("
            for child in varsub.children:
                formatted += self.format(child)
            formatted += ")"

        return formatted

    def format_arg_expansion(self, arg_expansion) -> str:
        # TODO: enforce in type?
        assert len(arg_expansion.children) == 1

        return "{*}" + self.format(arg_expansion.children[0])

    def format_list(self, _list) -> str:
        # TODO: implement once we know how to make indents work
        return ""

    def format_expression(self, expr) -> str:
        formatted = ""
        for child in expr.children:
            formatted += self.format(child)

        return formatted

    def format_braced_expression(self, expr) -> str:
        formatted = "{" + _STYLE_SPACES_IN_BRACES
        for child in expr.children:
            formatted += self.format(child)
        formatted += _STYLE_SPACES_IN_BRACES + "}"

        return formatted

    def format_paren_expression(self, expr) -> str:
        formatted = "("
        for child in expr.children:
            formatted += self.format(child)
        formatted += ")"

        return formatted

    def format_unary_op(self, expr):
        # TODO: enforce in type?
        assert len(expr.children) == 2

        return self.format(expr.children[0], expr.children[1])

    def format_binary_op(self, expr):
        # TODO: enforce in type?
        assert len(expr.children) == 3

        return " ".join([
            self.format(expr.children[0]),
            self.format(expr.children[1]),
            self.format(expr.children[2]),
        ])

    def format_ternary_op(self, expr):
        # TODO: enforce in type?
        assert len(expr.children) == 5

        return " ".join(
            self.format(expr.children[0]),
            self.format(expr.children[1]),
            self.format(expr.children[2]),
            self.format(expr.children[3]),
            self.format(expr.children[4]),
        )

    def format_function(self, function):
        # TODO: enforce in type?
        assert len(function.children) >= 1

        formatted_args = ", ".join(function.children[1:])
        return f"{function.children[0]}({formatted_args})"
