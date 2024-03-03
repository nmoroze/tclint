"""Classes for representing and interacting with Tcl syntax trees. """


class Visitor:
    """Abstract base class for Visitors that operate on syntax tree."""

    def visit_script(self, script):
        pass

    def visit_comment(self, comment):
        pass

    def visit_command(self, command):
        pass

    def visit_command_sub(self, command_sub):
        pass

    def visit_bare_word(self, word):
        pass

    def visit_braced_word(self, word):
        pass

    def visit_quoted_word(self, word):
        pass

    def visit_compound_bare_word(self, word):
        pass

    def visit_var_sub(self, var_sub):
        pass

    def visit_arg_expansion(self, arg_expansion):
        pass

    def visit_list(self, list):
        pass

    def visit_expression(self, expression):
        pass

    def visit_braced_expression(self, expression):
        pass

    def visit_paren_expression(self, expression):
        pass

    def visit_unary_op(self, unary_op):
        pass

    def visit_binary_op(self, binary_op):
        pass

    def visit_ternary_op(self, ternary_op):
        pass

    def visit_function(self, function):
        pass


class Node:
    """
    Invariants:
    - self.value is some sort of base Python type
    - self.children is a list of Node types
    """

    def __init__(self, *init, pos=None, end_pos=None):
        """pos: line, column of first character of parsed region (1-indexed)
        end_pos: line, column of first character after parsed region (1-indexed)
        """
        self.line = None
        self.col = None
        if pos is not None:
            self.line, self.col = pos
        self.end_pos = end_pos

        self.value = None
        if len(init) > 0 and not isinstance(init[0], Node):
            self.value = init[0]
            init = init[1:]

        if not all(isinstance(v, Node) for v in init):
            raise TypeError("Children must be Node instances")

        self.children = list(init)

    def add(self, node):
        self.children.append(node)

    @property
    def contents(self):
        """This is overloaded by word Nodes that may have concrete contents.

        TODO: I prefer the name value, but that's currently taken...
        """
        return None

    @property
    def contents_pos(self):
        """This is overloaded by word Nodes that may have concrete contents.

        Returns the position at which the contents start.

        TODO: consider combining with with `contents`?
        """
        return None

    def _pos_str(self):
        start_pos_str = "?"
        if self.pos is not None:
            start_pos_str = f"{self.pos[0]}:{self.pos[1]}"
        end_pos_str = "?"
        if self.end_pos is not None:
            end_pos_str = f"{self.end_pos[0]}:{self.end_pos[1]}"

        return f"  # {start_pos_str}-{end_pos_str}"

    def _make_str(self, indent=None, positions=False):
        if indent is not None:
            s = "  " * indent
        else:
            s = ""

        s += self.__class__.__name__
        s += "("

        if self.value:
            s += repr(self.value)
            if self.children:
                s += ", "

        if positions and self.children:
            s += self._pos_str()

        for i, child in enumerate(self.children):
            if indent is not None:
                s += "\n"
            s += child._make_str(
                indent=None if indent is None else indent + 1, positions=positions
            )
            if i < len(self.children) - 1:
                s += ", "
        s += ")"

        if positions and not self.children:
            s += self._pos_str()

        return s

    def pretty(self, positions=False):
        return self._make_str(indent=0, positions=positions)

    def __str__(self):
        return self._make_str()

    def __eq__(self, other):
        if self.value != other.value:
            return False

        if len(self.children) != len(other.children):
            return False
        for my_child, other_child in zip(self.children, other.children):
            if my_child != other_child:
                return False

        return True

    def diff(self, other, indent_depth=0):
        lines = []
        indent = "  " * indent_depth

        my_cls = self.__class__.__name__
        other_cls = other.__class__.__name__

        if my_cls != other_cls:
            lines += [f"{indent}-{my_cls}("]
            lines += [f"{indent}+{other_cls}("]
            return lines

        if self.value != other.value:
            lines += [f'{indent}-{my_cls}("{self.value}"']
            lines += [f'{indent}+{other_cls}("{other.value}"']
            return lines

        if len(self.children) != len(other.children):
            my_children = ",".join([
                child.__class__.__name__ for child in self.children
            ])
            other_children = ",".join([
                child.__class__.__name__ for child in other.children
            ])

            lines += [f"{indent}-{my_cls}({my_children})"]
            lines += [f"{indent}+{other_cls}({other_children})"]
            return lines

        if self.value is not None:
            lines += [f"{indent}{my_cls}({self.value}"]
        else:
            lines += [f"{indent}{my_cls}("]

        for my_child, other_child in zip(self.children, other.children):
            lines += my_child.diff(other_child, indent_depth=indent_depth + 1)

        lines += [f"{indent})"]

        return lines

    @property
    def pos(self):
        if self.line is None or self.col is None:
            return None

        return (self.line, self.col)

    def _recurse(self, visitor):
        for child in self.children:
            child.accept(visitor, recurse=True)


class Script(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # hack for spaces-in-braces check
        self.braced = False

    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_script(self)


class Comment(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_comment(self)


class Command(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_command(self)

    @property
    def routine(self):
        if len(self.children) == 0:
            return None
        return self.children[0].contents

    @property
    def args(self):
        if len(self.children) < 2:
            return []
        return self.children[1:]


class CommandSub(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_command_sub(self)


class BareWord(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_bare_word(self)

    @property
    def contents(self):
        return self.value

    @property
    def contents_pos(self):
        return self.pos


class BracedWord(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_braced_word(self)

    @property
    def contents(self):
        return self.value

    @property
    def contents_pos(self):
        return (self.line, self.col + 1)


class QuotedWord(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_quoted_word(self)

    @property
    def contents(self):
        """A QuotedWord with concrete contents is put in the tree as
        QuotedWord(BareWord()), so return contents of its child."""
        if len(self.children) > 1:
            return None
        if len(self.children) == 0:
            # weird special case to handle blank quoted string ("") - it doesn't
            # make sense to put in a child, but setting/returning the value is
            # also inconsistent
            return ""

        return self.children[0].contents

    @property
    def contents_pos(self):
        if self.contents is None:
            return None
        return (self.line, self.col + 1)


class CompoundBareWord(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_compound_bare_word(self)


class VarSub(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_var_sub(self)


class ArgExpansion(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_arg_expansion(self)


class List(Node):
    """This Node currently exists exclusively for implementing the switch
    command in a way that facilitates style checks. Might be nice to find
    another way to handle this that doesn't require a special Node."""

    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_list(self)


class Expression(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_expression(self)


class BracedExpression(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_braced_expression(self)


class ParenExpression(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_paren_expression(self)


class UnaryOp(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_unary_op(self)


class BinaryOp(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_binary_op(self)


class TernaryOp(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_ternary_op(self)


class Function(Node):
    def accept(self, visitor, recurse=False):
        if recurse:
            self._recurse(visitor)
        visitor.visit_function(self)
