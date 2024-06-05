from __future__ import annotations
from typing import Union, Optional, List

from ply import lex

# TODO: add -d/--debug to make-spec
DEBUG = False


def _dbg_print(msg):
    if DEBUG:
        print(msg)


# TODO: probably want to refactor lexer to make it look like lexer.py.


class Lexer:
    tokens = (
        "NEWLINE",
        "WS",
        "LBRACKET",
        "RBRACKET",
        "LPAREN",
        "RPAREN",
        "LBRACE",
        "RBRACE",
        "PIPE",
        "SWITCH",
        "VALUE",
    )

    def t_NEWLINE(self, t):
        r"\n"
        return t

    def t_WS(self, t):
        r"\s+"
        pass

    def t_LBRACKET(self, t):
        r"\["
        return t

    def t_RBRACKET(self, t):
        r"\]"
        return t

    def t_LPAREN(self, t):
        r"\("
        return t

    def t_RPAREN(self, t):
        r"\)"
        return t

    def t_LBRACE(self, t):
        r"\{"
        return t

    def t_RBRACE(self, t):
        r"\}"
        return t

    def t_PIPE(self, t):
        r"\|"
        return t

    def t_SWITCH(self, t):
        r"(-[^\[\]\s\|\(\)]+|>+)"
        return t

    def t_VALUE(self, t):
        r"[^\[\]\s\|\(\)\{\}]+"
        return t

    def t_error(self, t):
        print("Illegal character '%s'" % t.value[0])
        t.lexer.skip(1)

    def __init__(self, data):
        self.lexer = lex.lex(object=self)
        self.lexer.input(data)
        self.current = self.lexer.token()
        self.next_tok = self.lexer.token()

    def next(self):
        current = self.current
        self.current = self.next_tok
        self.next_tok = self.lexer.token()
        return current

    def token(self):
        return self.next()


ArgType = Union["Positional", "Switch", "OptionalArg", "ExclusiveArgs"]
ValueType = Union["AnyVal", "ExclusiveVals", "Literal", "ListVal"]


class Command:
    def __init__(self, name: str, args: Optional[List[ArgType]] = None):
        self.name = name
        self.args = []
        if args is not None:
            self.args = args

    def __str__(self):
        return f"{self.name} {' '.join(map(str, self.args))}"

    def __eq__(self, other):
        if not isinstance(other, Command):
            return False
        return (self.name == other.name) and (self.args == other.args)


class AnyVal:
    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if not isinstance(other, AnyVal):
            return False
        return self.name == other.name


class Positional:
    def __init__(self, value: ValueType):
        self.value = value

    def __str__(self):
        return str(self.value)

    def __eq__(self, other):
        if not isinstance(other, Positional):
            return False
        return self.value == other.value


class Switch:
    def __init__(self, name, value: Optional[ValueType] = None):
        self.name = name
        self.value = value

    def __str__(self):
        s = f"{self.name}"
        if self.value is not None:
            s += f" {self.value}"
        return s

    def __eq__(self, other):
        if not isinstance(other, Switch):
            return False
        return (self.name == other.name) and (self.value == other.value)


class ListVal:
    def __init__(self, items: Optional[List[str]] = None):
        self.items = []
        if items is not None:
            self.items = items

    def __str__(self):
        return "{" + " ".join(self.items) + "}"

    def __eq__(self, other):
        if not isinstance(other, ListVal):
            return False
        return self.items == other.items


class OptionalArg:
    def __init__(self, child: ArgType):
        self.child = child

    def __str__(self):
        return f"[{self.child}]"

    def __eq__(self, other):
        if not isinstance(other, OptionalArg):
            return False
        return self.child == other.child


class ExclusiveArgs:
    def __init__(self, choices: Optional[List[ArgType]] = None):
        self.choices = []
        if choices is not None:
            self.choices = choices

    def __str__(self):
        return "(" + " | ".join(map(str, self.choices)) + ")"

    def __eq__(self, other):
        if not isinstance(other, ExclusiveArgs):
            return False
        return self.choices == other.choices


class ExclusiveVals:
    def __init__(self, choices: Optional[List[Union[AnyVal, ListVal, Literal]]] = None):
        self.choices = []
        if choices is not None:
            self.choices = choices

    def __str__(self):
        return "(" + " | ".join(map(str, self.choices)) + ")"

    def __eq__(self, other):
        if not isinstance(other, ExclusiveVals):
            return False
        return self.choices == other.choices


class Literal:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f'"{self.value}"'

    def __eq__(self, other):
        if not isinstance(other, Literal):
            return False
        return self.value == other.value


def parse_help_entry(entry: str) -> Command:
    lexer = Lexer(entry)
    return parse_command(lexer)


def spec_from_help_entry(entry: str) -> dict:
    command = parse_help_entry(entry)
    return {command.name: make_spec(command)}


def parse_command(lexer: Lexer) -> Command:
    _dbg_print(f"parse_command({lexer.current})")
    tok = lexer.token()

    assert tok.type == "VALUE", f"Expected value, got {tok.type}"
    command = Command(tok.value)

    while lexer.current is not None and lexer.current.type != "NEWLINE":
        arg = parse_arg(lexer)
        command.args.append(arg)
    lexer.token()  # munch newline

    return command


def parse_arg(lexer: Lexer) -> ArgType:
    _dbg_print(f"parse_arg({lexer.current})")
    tok = lexer.current

    arg: Optional[ArgType] = None
    if tok.type == "LPAREN":
        lexer.token()
        arg = parse_arg(lexer)
        tok = lexer.token()
        assert tok.type == "RPAREN", f"expected closing paren, got {tok.type}"
        return arg
    elif tok.type == "LBRACKET":
        lexer.token()
        arg = OptionalArg(parse_arg(lexer))
        assert lexer.token().type == "RBRACKET", "expected closing bracket"
    elif tok.type == "SWITCH":
        lexer.token()
        value = None
        if lexer.current is not None and lexer.current.type in {
            "VALUE",
            "LPAREN",
            "LBRACE",
        }:
            value = parse_value(lexer)
        arg = Switch(tok.value, value)
    elif tok.type in {"VALUE", "LBRACE"}:
        arg = Positional(parse_value(lexer))

    assert arg is not None, f"Unexpected token {tok.type}"

    if lexer.current is not None and lexer.current.type == "PIPE":
        lexer.token()  # munch pipe

        exclusive = ExclusiveArgs()
        exclusive.choices.append(arg)

        next = parse_arg(lexer)
        if isinstance(next, ExclusiveArgs):
            # flatten this
            exclusive.choices.extend(next.choices)
        else:
            exclusive.choices.append(next)

        arg = exclusive

    return arg


def parse_value(lexer: Lexer) -> ValueType:
    _dbg_print(f"parse_value({lexer.current})")
    tok = lexer.next()
    val: ValueType
    if tok.type == "LPAREN":
        val = parse_value(lexer)
        assert lexer.token().type == "RPAREN"
        return val

    if tok.type == "LBRACE":
        val = ListVal()
        while lexer.current.type != "RBRACE":
            val.items.append(lexer.current.value)
            lexer.token()
        assert lexer.token().type == "RBRACE"
    else:
        assert tok.type == "VALUE", tok.type
        val = AnyVal(tok.value)

    if (
        lexer.current is not None
        and lexer.current.type == "PIPE"
        and lexer.next_tok is not None
        and lexer.next_tok.type in {"VALUE", "LBRACE"}
    ):
        lexer.next()  # munch pipe
        choices: List[Union[AnyVal, ListVal, Literal]] = [val]

        next = parse_value(lexer)
        if isinstance(next, ExclusiveVals):
            # flatten this
            choices.extend(next.choices)
        else:
            choices.append(next)

        make_literal = [isinstance(c, (AnyVal, Literal)) for c in choices].count(
            True
        ) > 1

        exclusive = ExclusiveVals()
        for choice in choices:
            if make_literal and isinstance(choice, AnyVal):
                exclusive.choices.append(Literal(choice.name))
            else:
                exclusive.choices.append(choice)

        return exclusive
    else:
        return val


def make_spec(command: Command) -> dict:
    spec = {"": {"min": 0, "max": 0}}

    for arg in command.args:
        if isinstance(arg, OptionalArg):
            _process_arg(arg.child, spec, optional=True)
        else:
            _process_arg(arg, spec, optional=False)

    for redirect in (">", ">>"):
        if redirect not in spec:
            spec[redirect] = {"required": False, "value": True, "repeated": False}

    return spec


def _process_arg(arg: ArgType, spec: dict, optional=False):
    if isinstance(arg, Positional):
        if not optional:
            spec[""]["min"] += 1
        spec[""]["max"] += 1
    elif isinstance(arg, Switch):
        spec[arg.name] = {
            "required": not optional,
            "value": arg.value is not None,
            "repeated": False,
        }
    elif isinstance(arg, ExclusiveArgs):
        has_positional = False
        for subarg in arg.choices:
            # bit of a hack, right now everything under ExclusiveArgs is treated
            # as effectively optional, so just pop into the child of the
            # Optional
            if isinstance(subarg, OptionalArg):
                subarg = subarg.child

            assert not isinstance(
                subarg, (ExclusiveArgs, OptionalArg)
            ), "Invalid argument type inside exclusive args"

            if isinstance(subarg, Switch):
                # TODO: make this stricter w/ exclusive field
                spec[subarg.name] = {
                    "required": False,
                    "value": subarg.value is not None,
                    "repeated": False,
                }
            elif isinstance(subarg, Positional):
                has_positional = True
        if has_positional:
            spec[""]["max"] += 1
