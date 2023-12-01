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
    TOK_VAR_CHARS,
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
)
from tclint.commands.builtin import CommandArgError, commands
from tclint.checks import CommandArgViolation


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
    def __init__(self, debug=False, cmd_sub=False, debug_indent=0):
        """cmd_sub = True indicates that the script will be terminated by ]"""
        self._debug = debug
        self._debug_indent = debug_indent
        self._cmd_sub = cmd_sub
        # TODO: better way to handle this?
        self.violations = []

    def debug(self, *msg):
        if self._debug:
            print("  " * self._debug_indent, end="")
            print(*msg)

    def parse(self, script, pos=None):
        lexer = Lexer(pos=pos)
        lexer.input(script)
        tree = self.parse_script(lexer)

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
        if routine not in commands:
            return args

        func = commands[routine]
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

        # This constraint ensures the parse tree represents the shape of the
        # code for style checking purposes (e.g. arg spacing)
        assert len(new_args) == len(args)

        return new_args

    def parse_script(self, ts):
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
                message=(
                    f"Expected newline or semicolon at {ts.pos()}, got {ts.value()}"
                ),
            )

        if self._cmd_sub and ts.type() is TOK_EOF:
            raise TclSyntaxError(
                "reached EOF without finding end of command substitution starting at"
                f" {pos}"
            )

        self._debug_indent -= 1

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
            self.violations.append(CommandArgViolation(str(e), pos))
            parsed_args = args

        return Command(routine, *parsed_args, pos=pos, end_pos=ts.pos())

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

        if ts.type() == TOK_EOF:
            raise TclSyntaxError(
                f"reached EOF without finding match for quote at {pos}"
            )

        res = word.resolve(ts.pos())

        ts.assert_(TOK_QUOTE)

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
                    "Reached EOF without finding match for brace at"
                    f" {expected_braces[-1]}"
                )

            if ts.type() == TOK_LBRACE:
                expected_braces.append(ts.pos())
            elif ts.type() == TOK_RBRACE:
                try:
                    expected_braces.pop()
                except IndexError:
                    raise TclSyntaxError(
                        f"Found closing brace at {ts.pos()} without matching open brace"
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
                        f"Reached EOF without finding match for brace at {brace_pos}"
                    )
                var += ts.value()
                ts.next()
            ts.next()

            return VarSub(var, pos=pos, end_pos=ts.pos())

        while ts.type() in {TOK_VAR_CHARS, TOK_NAMESPACE_SEP}:
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
                        f"Reached EOF without finding match for paren at {paren_pos}"
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
        script = self.parse_script(ts)
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

                ts.assert_(TOK_QUOTE)

                list_node.add(QuotedWord(word, pos=quote_word_pos, end_pos=ts.pos()))
            else:
                pos = ts.pos()
                contents = ""
                while ts.type() not in DELIMITERS:
                    contents += ts.value()
                    ts.next()
                list_node.add(BareWord(contents, pos=pos, end_pos=ts.pos()))

        return list_node

    def parse_expression(self, node):
        return Expression(node.contents, pos=node.pos, end_pos=node.end_pos)
