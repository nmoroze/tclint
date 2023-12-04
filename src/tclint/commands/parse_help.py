from ply import lex

class _Lexer():
    tokens = (
        "WS", "NEWLINE", "LBRACKET", "RBRACKET", "SWITCH", "VALUE", "PIPE"
    )

    def t_WS(self, t):
        r"\s+"
        return t

    def t_LBRACKET(self, t):
        r"\["
        return t

    def t_RBRACKET(self, t):
        r"\]"
        return t

    def t_PIPE(self, t):
        r"\|"
        return t

    def t_SWITCH(self, t):
        r"(-[^\[\]\s]+|>+)"
        return t

    def t_VALUE(self, t):
        r"[^\[\]\s]+"
        return t

def parse_help_file(path):
    with open(path, 'r') as f:
        data = f.read()

    m = _Lexer()
    lexer = lex.lex(object=m)
    lexer.input(data)

    commands = {}
    while True:
        command = parse_command(lexer)
        if command is None:
            break
        commands.update(command)

    return commands

def parse_command(lexer):
    tok = lexer.token()
    # print(tok)
    if tok is None:
        return None

    assert tok.type == "VALUE", tok.type
    command = tok.value

    tok = lexer.token()
    assert tok.type == "WS"
    if '\n' in tok.value and len(tok.value) == 1:
        return {command: {"": {"required": False, "value": 0}}}

    args = parse_args(lexer)

    return {command: args}

def parse_args(lexer, optional=False):
    args = {"": {"required": False, "value": 0}}
    last_switch = ""

    while True:
        tok = lexer.token()
        # print(tok)
        if tok.type == "LBRACKET":
            args.update(parse_args(lexer, optional=True))
        elif tok.type == "SWITCH":
            last_switch = tok.value
            args[last_switch] = {
                "required": not optional,
                "value": 0
            }
        elif tok.type == "VALUE":
            if last_switch != "":
                assert not args[last_switch]["value"]

            if args[last_switch]["value"] > 0:
                assert args[last_switch]["required"] != optional

            args[last_switch]["required"] = not optional
            args[last_switch]["value"] += 1
            last_switch = ""
        elif (optional and tok.type == "RBRACKET") or (tok.type == "WS" and tok.value == "\n"):
            break

    return args

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter()
    pp.pprint(parse_help_file('openroad-help.txt'))
