import ply.lex as lex
from typing import Tuple

TOK_BACKSLASH_NEWLINE = "BACKSLASH_NEWLINE"
TOK_BACKSLASH_SUB = "BACKSLASH_SUB"
TOK_NEWLINE = "NEWLINE"
TOK_SEMI = "SEMI"
TOK_WS = "WS"
TOK_QUOTE = "QUOTE"
TOK_ARG_EXPANSION = "ARG_EXPANSION"
TOK_LBRACE = "LBRACE"
TOK_RBRACE = "RBRACE"
TOK_STAR = "STAR"
TOK_LBRACKET = "LBRACKET"
TOK_RBRACKET = "RBRACKET"
TOK_DOLLAR = "DOLLAR"
TOK_LPAREN = "LPAREN"
TOK_RPAREN = "RPAREN"
TOK_HASH = "HASH"
TOK_ALPHA_CHARS = "ALPHA_CHARS"
TOK_NUM_CHARS = "NUM_CHARS"
TOK_NAMESPACE_SEP = "NAMESPACE_SEP"
TOK_CHAR = "CHAR"
TOK_CONTENTS = "CONTENTS"
TOK_EOF = None

STATE_BRACEDWORD = "bracedword"


class TclSyntaxError(Exception):
    def __init__(self, message, start: Tuple[int, int], end: Tuple[int, int]):
        super().__init__(message)
        self.start = start
        self.end = end


class _LexTable:
    tokens = (
        TOK_BACKSLASH_NEWLINE,
        TOK_BACKSLASH_SUB,
        TOK_NEWLINE,
        TOK_SEMI,
        TOK_WS,
        TOK_QUOTE,
        TOK_ARG_EXPANSION,
        TOK_LBRACE,
        TOK_RBRACE,
        TOK_STAR,
        TOK_LBRACKET,
        TOK_RBRACKET,
        TOK_DOLLAR,
        TOK_LPAREN,
        TOK_RPAREN,
        TOK_HASH,
        TOK_ALPHA_CHARS,
        TOK_NUM_CHARS,
        TOK_NAMESPACE_SEP,
        TOK_CHAR,
        TOK_CONTENTS,
    )

    # This defines a conditional lexing state for parsing braced words. This is a
    # performance optimization; since there are few special characters in this context,
    # we can use a smaller set of tokens to parse them faster. This has a large impact
    # since most Tcl programs have a large number of braced words. Any token with
    # `bracedword` in its name is included in this state. Tokens that are included in
    # this state and the default state also include `INITIAL` in their name.
    states = ((STATE_BRACEDWORD, "exclusive"),)

    def _tok(self, t):
        pos = (t.lexer.lineno, t.lexer.colno)
        t.lexer.lineno += t.value.count("\n")
        index = t.value.rfind("\n")
        if index == -1:
            t.lexer.colno += len(t.value)
        else:
            remaining = t.value[index + 1 :]
            t.lexer.colno = len(remaining) + 1

        t.value = (t.value, pos)
        return t

    # Priority important
    def t_bracedword_INITIAL_BACKSLASH_NEWLINE(self, t):
        r"\\\n"
        return self._tok(t)

    # Priority important
    def t_bracedword_INITIAL_BACKSLASH_SUB(self, t):
        r"\\."
        return self._tok(t)

    def t_NEWLINE(self, t):
        r"\n"
        return self._tok(t)

    def t_SEMI(self, t):
        r";"
        return self._tok(t)

    # TODO: should use \s?
    def t_WS(self, t):
        r"[\t\v\f\r ]+"
        return self._tok(t)

    def t_QUOTE(self, t):
        r'"'
        return self._tok(t)

    # Must be higher priority than LBRACE
    def t_ARG_EXPANSION(self, t):
        r"\{\*\}"
        return self._tok(t)

    def t_bracedword_INITIAL_LBRACE(self, t):
        r"\{"
        return self._tok(t)

    def t_bracedword_INITIAL_RBRACE(self, t):
        r"\}"
        return self._tok(t)

    def t_STAR(self, t):
        r"\*"
        return self._tok(t)

    def t_LBRACKET(self, t):
        r"\["
        return self._tok(t)

    def t_RBRACKET(self, t):
        r"\]"
        return self._tok(t)

    def t_DOLLAR(self, t):
        r"\$"
        return self._tok(t)

    def t_LPAREN(self, t):
        r"\("
        return self._tok(t)

    def t_RPAREN(self, t):
        r"\)"
        return self._tok(t)

    def t_HASH(self, t):
        r"\#"
        return self._tok(t)

    # Valid non-numeric chars in variable names
    def t_ALPHA_CHARS(self, t):
        r"[A-Za-z_]+"
        return self._tok(t)

    # Valid numeric chars in variable names
    # This is split up from the above to facilitate expression parsing, since
    # e.g. 1eq1 can't be a single token.
    def t_NUM_CHARS(self, t):
        r"[0-9]+"
        return self._tok(t)

    def t_NAMESPACE_SEP(self, t):
        r"::+"
        return self._tok(t)

    def t_bracedword_CONTENTS(self, t):
        r"[^{}\\]+"
        return self._tok(t)

    # Catch-all. TODO: inefficient, should probably munch multiple chars
    def t_CHAR(self, t):
        r"."
        return self._tok(t)

    # Error handling rule
    # TODO: do we need this? since we have a catch-all...
    # there is a warning
    def t_bracedword_INITIAL_error(self, t):
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)

    def __init__(self):
        self.lexer = lex.lex(object=self)
        self.lexer.lineno = 1
        self.lexer.colno = 1

    def new_lexer(self, pos=None):
        lexer = self.lexer.clone()
        lexer.lineno = 1
        lexer.colno = 1

        if pos is not None:
            line, col = pos
            lexer.lineno = line
            lexer.colno = col

        return lexer


# Calling `lex.lex()` performs an expensive reflection process to generate the lexer.
# This singleton class holds a preinitialized lexer that can then be cloned to create
# individual instances.
LexTable = _LexTable()


class Lexer:
    def __init__(self, pos=None):
        self.lexer = LexTable.new_lexer(pos)
        self.current = None

    def input(self, text):
        self.lexer.input(text)
        self.current = self.lexer.token()

    def type(self):
        if self.current is None:
            return TOK_EOF
        return self.current.type

    def value(self):
        if self.current is None:
            return None
        return self.current.value[0]

    def pos(self):
        if self.current is None:
            return (self.lexer.lineno, self.lexer.colno)
        return self.current.value[1]

    def next(self):
        self.current = self.lexer.token()

    def expect(self, *tokens, message, pos):
        if self.type() not in tokens:
            self.next()  # munch another token to update position
            raise TclSyntaxError(message, pos, self.pos())

        self.next()

    def assert_(self, *tokens):
        assert self.current.type in tokens
        self.next()
