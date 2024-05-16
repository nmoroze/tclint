import string
import re

from tclint.lexer import (
    Lexer,
    TclSyntaxError,
    TOK_BACKSLASH_NEWLINE,
    TOK_NEWLINE,
    TOK_SEMI,
    TOK_WS,
    TOK_QUOTE,
    TOK_ARG_EXPANSION,
    TOK_LBRACE,
    TOK_RBRACE,
    TOK_LBRACKET,
    TOK_RBRACKET,
    TOK_DOLLAR,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_HASH,
    TOK_ALPHA_CHARS,
    TOK_NUM_CHARS,
    TOK_NAMESPACE_SEP,
    TOK_EOF,
)
from tclint.syntax_tree import (
    Script,
    Comment,
    Command,
    CommandSub,
    ArgExpansion,
    VarSub,
    BareWord,
    BracedWord,
    QuotedWord,
    CompoundBareWord,
    List,
    Expression,
    BracedExpression,
    ParenExpression,
    UnaryOp,
    BinaryOp,
    TernaryOp,
    Function,
)
from tclint.commands import CommandArgError, get_commands
from tclint.violations import Rule, Violation


def _strip_ws(parse_func):
    """Decorator used by expression parser for stripping whitespace around a node."""

    def func(parser, ts):
        while ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE, TOK_NEWLINE}:
            ts.next()

        node = parse_func(parser, ts)

        while ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE, TOK_NEWLINE}:
            ts.next()

        return node

    return func


class _Word:
    """Helper class for constructing Word nodes out of multiple segments."""

    def __init__(self):
        self.segments = []
        self.current_segment = ""
        self.current_start = None

    def add_tok(self, tok):
        if self.current_start is None:
            self.current_start = tok.value[1]
        self.current_segment += tok.value[0]

    def add_node(self, node):
        if self.current_segment != "":
            self.segments.append(
                BareWord(self.current_segment, pos=self.current_start, end_pos=node.pos)
            )
            self.current_segment = ""
            self.current_start = None
        self.segments.append(node)

    def resolve(self, end_pos):
        if self.current_segment:
            self.segments.append(
                BareWord(self.current_segment, pos=self.current_start, end_pos=end_pos)
            )

        return self.segments


class Parser:
    def __init__(self, debug=False, command_plugins=None):
        self._debug = debug
        self._debug_indent = 0
        # self._cmd_sub = True indicates that the script will be terminated by ]"""
        self._cmd_sub = False
        # TODO: better way to handle this?
        self.violations = []

        if command_plugins is None:
            command_plugins = []
        self._commands = get_commands(command_plugins)

    def debug(self, *msg):
        if self._debug:
            print("  " * self._debug_indent, end="")
            print(*msg)

    def parse(self, script, pos=None):
        lexer = Lexer(pos=pos)
        lexer.input(script)
        tree = self._parse_script(lexer)

        return tree

    def _parse_command_args(self, routine, args):
        """Since many built-in Tcl commands take in Tcl scripts or expressions
        as arguments, building a complete parse tree requires checking command
        names and possibly parsing their arguments.

        The node of any argument that gets parsed by this method is replaced with
        the parse tree of that argument. Since this process requires checking
        the arguments provided to these commands, this method may report lint
        violations.

        This parsing process is analogous to how the Tcl interpreter interprets
        scripts, and better handles weird edge cases compared to a traditional
        parsing technique. For example, this may look like valid Tcl:

        proc foo {a} {
            # output }
            puts "}"
        }

        But really, it is invalid since the } in the comment terminates the body
        of the proc - Tcl blindly constructs the body of the proc until it
        reaches the first }. tclint handles this correctly.
        """
        if routine not in self._commands:
            return args

        func = self._commands[routine]
        if func is None:
            return args

        try:
            new_args = func(args, self)
        except CommandArgError as e:
            raise e
        except Exception:
            if self.debug:
                raise
            raise CommandArgError(
                f"error parsing command arguments, possibly malformed {routine} command"
            )

        if new_args is None:
            return args

        return new_args

    def parse_script(self, node):
        if node.contents is None:
            raise CommandArgError(
                "expected braced word or word without substitutions in argument"
                " interpreted as script"
            )

        cmd_sub = self._cmd_sub
        self._cmd_sub = False
        script = self.parse(node.contents, pos=node.contents_pos)
        if isinstance(node, BracedWord):
            script.braced = True
        self._cmd_sub = cmd_sub

        script.line = node.line
        script.col = node.col
        script.end_pos = node.end_pos

        return script

    def _parse_script(self, ts):
        self.debug(f"parse_script({ts.current})")
        self._debug_indent += 1
        pos = ts.pos()

        if self._cmd_sub:
            script = CommandSub(pos=pos)
        else:
            script = Script(pos=pos)

        while ts.type() is not TOK_EOF:
            if ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE}:
                # strip whitespace at start of command
                ts.next()
                continue

            if ts.type() == TOK_HASH:
                script.add(self.parse_comment(ts))
            else:
                cmd = self.parse_command(ts)
                if cmd is not None:
                    script.add(cmd)

            # when in command sub mode, a script is terminated by ]
            if self._cmd_sub and ts.type() == TOK_RBRACKET:
                return script

            ts.expect(
                TOK_EOF,
                TOK_NEWLINE,
                TOK_SEMI,
                message=f"expected newline or semicolon, got {ts.value()}",
                pos=ts.pos(),
            )

        if self._cmd_sub and ts.type() is TOK_EOF:
            raise TclSyntaxError(
                "reached EOF without finding end of command substitution", pos
            )

        self._debug_indent -= 1

        script.end_pos = ts.pos()

        return script

    def parse_comment(self, ts):
        self.debug(f"parse_comment({ts.current})")
        pos = ts.pos()

        ts.assert_(TOK_HASH)

        value = ""
        while ts.type() not in {TOK_NEWLINE, TOK_EOF}:
            value += ts.value()
            ts.next()

        return Comment(value, pos=pos, end_pos=ts.pos())

    def parse_command(self, ts):
        self.debug(f"parse_command({ts.current})")
        self._debug_indent += 1
        pos = ts.pos()

        routine = self.parse_word(ts)
        if routine is None:
            self._debug_indent -= 1
            return None

        args = []
        while True:
            if ts.type() not in {TOK_WS, TOK_BACKSLASH_NEWLINE}:
                break

            while ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE}:
                ts.next()

            word = self.parse_word(ts)
            if word is None:
                break

            args.append(word)

        self._debug_indent -= 1

        try:
            parsed_args = self._parse_command_args(routine.contents, args)
        except CommandArgError as e:
            self.violations.append(Violation(Rule.COMMAND_ARGS, str(e), pos))
            parsed_args = args

        children = [routine, *parsed_args]
        # We need to inherit end pos of last child to prevent us from counting
        # extra whitespace at end of command, which is important for
        # spaces-in-braces check.
        return Command(*children, pos=pos, end_pos=children[-1].end_pos)

    def parse_word(self, ts):
        self.debug(f"parse_word({ts.current})")
        if ts.type() == TOK_ARG_EXPANSION:
            return self.parse_arg_expansion(ts)
        elif ts.type() == TOK_LBRACE:
            return self.parse_braced_word(ts)
        elif ts.type() == TOK_QUOTE:
            return self.parse_quoted_word(ts)
        else:
            return self.parse_bare_word(ts)

    def parse_arg_expansion(self, ts):
        self.debug(f"parse_arg_expansion({ts.current})")
        pos = ts.pos()

        ts.assert_(TOK_ARG_EXPANSION)

        # Arg expansion is just a regular braced word if followed by whitespace
        if ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE, TOK_NEWLINE, TOK_EOF}:
            return BracedWord("*", pos=pos, end_pos=ts.pos())

        return ArgExpansion(self.parse_word(ts), pos=pos, end_pos=ts.pos())

    def parse_quoted_word(self, ts):
        self.debug(f"parse_quoted_word({ts.current})")
        self._debug_indent += 1
        pos = ts.pos()

        ts.assert_(TOK_QUOTE)

        word = _Word()
        while ts.type() not in {TOK_QUOTE, TOK_EOF}:
            if ts.type() == TOK_DOLLAR:
                dollar_tok = ts.current
                var_sub = self.parse_var_sub(ts)
                if var_sub:
                    word.add_node(var_sub)
                else:
                    word.add_tok(dollar_tok)
            elif ts.type() == TOK_LBRACKET:
                command_sub = self.parse_command_sub(ts)
                word.add_node(command_sub)
            else:
                word.add_tok(ts.current)
                ts.next()

        res = word.resolve(ts.pos())

        ts.expect(
            TOK_QUOTE, message="reached EOF without finding match for quote", pos=pos
        )

        self._debug_indent -= 1

        if not res:
            res = []

        return QuotedWord(*res, pos=pos, end_pos=ts.pos())

    def parse_braced_word(self, ts):
        self.debug(f"parse_braced_word({ts.current})")
        pos = ts.pos()

        ts.assert_(TOK_LBRACE)

        word = ""
        # store position for each brace we want to match, facilitating good
        # error messages
        expected_braces = [pos]
        while True:
            if ts.type() == TOK_EOF:
                raise TclSyntaxError(
                    "reached EOF without finding match for brace", expected_braces[-1]
                )

            if ts.type() == TOK_LBRACE:
                expected_braces.append(ts.pos())
            elif ts.type() == TOK_RBRACE:
                try:
                    expected_braces.pop()
                except IndexError:
                    raise TclSyntaxError(
                        "found closing brace without matching open brace", ts.pos()
                    )

                if len(expected_braces) == 0:
                    ts.next()
                    break
            word += ts.value()
            ts.next()

        end_pos = ts.pos()
        return BracedWord(word, pos=pos, end_pos=end_pos)

    def parse_bare_word(self, ts):
        self.debug(f"parse_bare_word({ts.current})")
        self._debug_indent += 1
        pos = ts.pos()

        word = _Word()
        delimiters = [TOK_WS, TOK_BACKSLASH_NEWLINE, TOK_NEWLINE, TOK_SEMI, TOK_EOF]

        # In command sub mode, words are ended by ]
        # TODO: consider pushing this down via argument to remove it as a member
        if self._cmd_sub:
            delimiters.append(TOK_RBRACKET)

        while ts.type() not in delimiters:
            if ts.type() == TOK_DOLLAR:
                dollar_tok = ts.current
                var_sub = self.parse_var_sub(ts)
                if var_sub:
                    word.add_node(var_sub)
                else:
                    word.add_tok(dollar_tok)
            elif ts.type() == TOK_LBRACKET:
                command_sub = self.parse_command_sub(ts)
                word.add_node(command_sub)
            else:
                word.add_tok(ts.current)
                ts.next()

        res = word.resolve(ts.pos())

        self._debug_indent -= 1

        if not res:
            return None
        if len(res) == 1:
            return res[0]
        return CompoundBareWord(*res, pos=pos, end_pos=ts.pos())

    def parse_var_sub(self, ts):
        self.debug(f"parse_var_sub({ts.current})")
        pos = ts.pos()

        ts.assert_(TOK_DOLLAR)

        var = ""
        if ts.type() == TOK_LBRACE:
            brace_pos = ts.pos()
            ts.next()
            while ts.type() != TOK_RBRACE:
                if ts.type() is TOK_EOF:
                    raise TclSyntaxError(
                        "reached EOF without finding match for brace", brace_pos
                    )
                var += ts.value()
                ts.next()
            ts.next()

            return VarSub(var, pos=pos, end_pos=ts.pos())

        while ts.type() in {TOK_ALPHA_CHARS, TOK_NUM_CHARS, TOK_NAMESPACE_SEP}:
            var += ts.value()
            ts.next()

        if not var:
            return None

        index_nodes = []
        if ts.type() == TOK_LPAREN:
            paren_pos = ts.pos()
            index = _Word()
            ts.next()
            while ts.type() != TOK_RPAREN:
                if ts.type() == TOK_EOF:
                    raise TclSyntaxError(
                        "reached EOF without finding match for paren", paren_pos
                    )
                if ts.type() == TOK_DOLLAR:
                    dollar_tok = ts.current
                    var_sub = self.parse_var_sub(ts)
                    if var_sub:
                        index.add_node(var_sub)
                    else:
                        index.add_tok(dollar_tok)
                elif ts.type() == TOK_LBRACKET:
                    command_sub = self.parse_command_sub(ts)
                    index.add_node(command_sub)
                else:
                    index.add_tok(ts.current)
                    ts.next()

            index_nodes = index.resolve(ts.pos())
            ts.next()

        var_sub = VarSub(var, pos=pos, end_pos=ts.pos())

        for index_segment in index_nodes:
            var_sub.add(index_segment)

        return var_sub

    def parse_command_sub(self, ts):
        self.debug(f"parse_command_sub({ts.current})")
        self._debug_indent += 1

        pos = ts.pos()
        ts.assert_(TOK_LBRACKET)

        saved_cmd_sub = self._cmd_sub
        self._cmd_sub = True
        script = self._parse_script(ts)
        self._cmd_sub = saved_cmd_sub

        ts.assert_(TOK_RBRACKET)
        end_pos = ts.pos()

        script.line = pos[0]
        script.col = pos[1]
        script.end_pos = end_pos

        self._debug_indent -= 1
        return script

    def parse_list(self, node):
        """Parse contents of node as Tcl list. This is a distinct entry point
        that doesn't get used when generating the main syntax tree, but is used
        in command-specific argument parsing.
        """
        if node.contents is None:
            return None

        # Hack: we know contents start 1 col over, since first char denotes the list
        ts = Lexer(pos=(node.line, node.col + 1))
        ts.input(node.contents)

        DELIMITERS = {TOK_WS, TOK_BACKSLASH_NEWLINE, TOK_NEWLINE}

        list_node = List(pos=node.pos, end_pos=node.end_pos)
        while ts.type() is not TOK_EOF:
            while ts.type() in DELIMITERS:
                ts.next()

            if ts.type() is TOK_EOF:
                break

            if ts.type() == TOK_LBRACE:
                # we can reuse parse_braced_word, since it doesn't use
                # substitutions in any case
                list_node.add(self.parse_braced_word(ts))
            elif ts.type() == TOK_QUOTE:
                quote_word_pos = ts.pos()

                ts.assert_(TOK_QUOTE)

                bare_word_pos = ts.pos()
                contents = ""
                while ts.type() not in {TOK_QUOTE, TOK_EOF}:
                    contents += ts.value()
                    ts.next()
                word = BareWord(contents, pos=bare_word_pos, end_pos=ts.pos())

                ts.expect(
                    TOK_QUOTE,
                    message="reached EOF without finding match for quote",
                    pos=quote_word_pos,
                )

                list_node.add(QuotedWord(word, pos=quote_word_pos, end_pos=ts.pos()))
            else:
                pos = ts.pos()
                contents = ""
                while ts.type() not in {*DELIMITERS, TOK_EOF}:
                    contents += ts.value()
                    ts.next()
                list_node.add(BareWord(contents, pos=pos, end_pos=ts.pos()))

        return list_node

    def parse_expression(self, node):
        if node.contents is None:
            raise CommandArgError(
                "expected braced word or word without substitutions in argument"
                " interpreted as expr"
            )

        ts = Lexer(pos=node.contents_pos)
        ts.input(node.contents)

        contents = self._parse_expression(ts)
        if isinstance(node, BracedWord):
            return BracedExpression(contents, pos=node.pos, end_pos=node.end_pos)

        return Expression(contents, pos=node.pos, end_pos=node.end_pos)

    @_strip_ws
    def _parse_expression(self, ts):
        op1 = self._parse_operand(ts)
        expr = None

        # last condition is hack to break out of expression in case we're in ternary op
        if ts.type() not in {TOK_EOF, TOK_RPAREN} and ts.value() not in {":", ","}:
            if ts.value() == "?":
                expr = TernaryOp(pos=op1.pos)
                expr.add(op1)

                # weird hack to record operator
                n = BareWord("?", pos=ts.pos())
                ts.next()
                n.end_pos = ts.pos()
                expr.add(n)

                op2 = self._parse_expression(ts)
                expr.add(op2)
                if ts.value() != ":":
                    raise TclSyntaxError(
                        "expected ':' to continue ternary expression", ts.pos()
                    )

                # weird hack again
                n = BareWord(":", pos=ts.pos())
                ts.next()
                n.end_pos = ts.pos()
                expr.add(n)

                op3 = self._parse_expression(ts)
                expr.add(op3)
            else:
                expr = BinaryOp(pos=op1.pos)
                expr.add(op1)

                operator = self._parse_operator(ts)
                expr.add(operator)

                op2 = self._parse_expression(ts)
                expr.add(op2)

            if ts.type() != TOK_RPAREN and ts.value() not in {":", ","}:
                ts.expect(TOK_EOF, message="expected end of expression", pos=ts.pos())

        if expr is None:
            return op1

        expr.end_pos = expr.children[-1].end_pos
        return expr

    @_strip_ws
    def _parse_operand(self, ts):
        if ts.type() == TOK_DOLLAR:
            return self.parse_var_sub(ts)
        if ts.type() == TOK_QUOTE:
            return self.parse_quoted_word(ts)
        if ts.type() == TOK_LBRACE:
            return self.parse_braced_word(ts)
        if ts.type() == TOK_LBRACKET:
            return self.parse_command_sub(ts)
        if ts.type() == TOK_LPAREN:
            expr = ParenExpression(pos=ts.pos())
            ts.next()
            expr.add(self._parse_expression(ts))
            ts.expect(
                TOK_RPAREN,
                message="reached EOF without finding match for paren",
                pos=expr.pos,
            )
            expr.end_pos = ts.pos()
            return expr
        if ts.value() in {"-", "+", "~", "!"}:
            operator = ts.value()
            operator_pos = ts.pos()
            ts.next()
            op = UnaryOp(pos=operator_pos)
            op.add(BareWord(operator, pos=operator_pos, end_pos=ts.pos())),
            op.add(self._parse_operand(ts))
            # Since _parse_operand() munches whitespace after the operand, we
            # set the end of the UnaryOp to the end of the operand rather than
            # ts.pos(). Otherwise, the bounds of the UnaryOp would include all
            # that whitespace.
            op.end_pos = op.children[-1].end_pos
            return op

        # If none of these, collect tokens that may comprise an operand
        operand = ""
        operand_pos = ts.pos()

        # First, we want to check for numeric operands (either ints or numeric
        # floats) by consuming tokens as long as they comprise the prefix of a
        # numeric operand
        while ts.type() != TOK_EOF and (
            _is_int_prefix(operand + ts.value())
            or _is_float_prefix(operand + ts.value())
        ):
            operand += ts.value()
            ts.next()

        # Next, we check if we've consumed an entire numeric literal. If so, we
        # move on. If not, we keep consuming tokens that may correspond to a
        # valid bareword (pretty much just alphanumeric chars).
        if not (_is_int_literal(operand) or _is_float_literal(operand)):
            while ts.type() in {TOK_ALPHA_CHARS, TOK_NUM_CHARS}:
                operand += ts.value()
                ts.next()

        # The above method is a little hacky. Note that it doesn't parse things
        # exactly the same as Tcl. E.g. if a script includes `expr {1foo}`,
        # tclint will report an invalid operator "foo", whereas tclsh will
        # report an invalid bareword "1foo". Despite reporting them differently
        # both tools should still catch the same syntax errors, since there are
        # no legal barewords that begin with a numeric literal prefix, and tclsh
        # will stop parsing numeric operands if they're actually followed by a
        # legal operator (e.g. `expr {1eq1}` will be handled properly).

        is_func = _is_function(operand)

        if not (
            _is_int_literal(operand)
            or _is_float_literal(operand)
            or _is_bool_literal(operand)
            or is_func
        ):
            raise TclSyntaxError(
                f"invalid bareword in expression: {operand}", operand_pos
            )

        node = BareWord(operand, pos=operand_pos, end_pos=ts.pos())

        if is_func:
            node = self._parse_function(ts, node)

        return node

    def _parse_operator(self, ts):
        pos = ts.pos()

        # hacky logic to handle parsing legal operators

        if ts.value() in {"*", "&", "|"}:
            # one or two of these characters are legal operators
            operator = ts.value()
            ts.next()
            if ts.value() == operator:
                operator += ts.value()
                ts.next()
        elif ts.value() in {"<", ">"}:
            operator = ts.value()
            ts.next()
            if ts.value() in {operator, "="}:
                operator += ts.value()
                ts.next()
        elif ts.value() in {"=", "!"}:
            operator = ts.value()
            ts.next()
            if ts.value() != "=":
                raise TclSyntaxError(f"invalid operator in expression: {operator}", pos)
            operator += ts.value()
            ts.next()
        elif ts.value() in {"*", "/", "%", "+", "-", "^", "eq", "ne", "in", "ni"}:
            operator = ts.value()
            ts.next()
        else:
            raise TclSyntaxError(f"invalid operator in expression: {ts.value()}", pos)

        return BareWord(operator, pos=pos, end_pos=ts.pos())

    def _parse_function(self, ts, name_node):
        func = Function(pos=name_node.pos)

        func.add(name_node)

        while ts.type() in {TOK_WS, TOK_BACKSLASH_NEWLINE}:
            ts.next()

        ts.expect(
            TOK_LPAREN,
            message="expected open paren after function name",
            pos=name_node.pos,
        )

        delims = {TOK_RPAREN, TOK_EOF}

        if ts.type() not in delims:
            arg = self._parse_expression(ts)
            func.add(arg)

        while ts.type() not in delims:
            if ts.value() != ",":
                raise TclSyntaxError(
                    "expected comma between function arguments", ts.pos()
                )

            # adding comma may seem a little weird since it's non-functional,
            # but this lets us store comma position for style checks
            comma = BareWord(",", pos=ts.pos())
            ts.next()
            comma.end_pos = ts.pos()
            func.add(comma)

            arg = self._parse_expression(ts)
            func.add(arg)

        ts.expect(
            TOK_RPAREN,
            message="expected close paren after function arguments",
            pos=name_node.pos,
        )
        func.end_pos = ts.pos()

        return func


def _all(_list, non_empty=False):
    """Like all(), but if non_empty is True, list must also have at least 1 element."""
    if non_empty and len(_list) == 0:
        return False
    return all(_list)


def _is_int(operand, full=False):
    """Returns whether operand is a valid Tcl integer literal.

    If full is False, will also return True if operand is the prefix of an
    integer literal.  An empty string is not a valid full literal, but is a
    valid prefix.
    """
    # prefixes
    if operand.startswith("0b"):
        return _all([digit in "01" for digit in operand[2:]], non_empty=full)
    if operand.startswith("0o"):
        return _all(
            [digit in string.octdigits for digit in operand[2:]], non_empty=full
        )
    if operand.startswith("0x"):
        return _all(
            [digit in string.hexdigits for digit in operand[2:]], non_empty=full
        )
    if operand.startswith("0"):
        # fun fact: apparently a lone 0 prefix is interpreted as octal
        return _all(
            [digit in string.octdigits for digit in operand[1:]], non_empty=full
        )

    return _all([digit in string.digits for digit in operand], non_empty=full)


def _is_int_literal(operand):
    return _is_int(operand, full=True)


def _is_int_prefix(operand):
    return _is_int(operand, full=False)


def _is_float_literal(operand):
    if operand.lower() in {"nan", "inf"}:
        return True

    return (
        operand != "" and re.fullmatch(r"\d*\.?\d*([Ee][+-]?\d+)?", operand) is not None
    )


def _is_float_prefix(operand):
    """Returns whether operand is the prefix of a valid numeric float literal."""
    return re.fullmatch(r"\d*\.?\d*([Ee][+-]?)?\d*", operand) is not None


def _is_bool_literal(operand):
    return operand in {"false", "no", "off", "true", "yes", "on"}


# map of function names to # arguments accepted
# None indicates 1 or more arguments
# TODO: use these values in an actual separate check. they might want to live elsewhere
_FUNCTIONS = {
    "abs": 1,
    "acos": 1,
    "asin": 1,
    "atan": 1,
    "atan2": 2,
    "bool": 1,
    "ceil": 1,
    "cos": 1,
    "cosh": 1,
    "double": 1,
    "entier": 1,
    "exp": 1,
    "floor": 1,
    "fmod": 2,
    "hyopt": 2,
    "int": 1,
    "isqrt": 1,
    "log": 1,
    "log10": 1,
    "max": None,
    "min": None,
    "pow": 2,
    "rand": 0,
    "round": 1,
    "sin": 1,
    "sinh": 1,
    "sqrt": 1,
    "srand": 1,
    "tan": 1,
    "tanh": 1,
    "wide": 1,
}


def _is_function(operand):
    return operand in _FUNCTIONS.keys()
