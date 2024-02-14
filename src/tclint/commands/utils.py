from tclint.syntax_tree import ArgExpansion, QuotedWord, BracedWord


class CommandArgError(Exception):
    pass


def parse_script_arg(arg, parser):
    # TODO: feels like parser should handle this more cleanly
    # (particularly the end_pos)
    contents = arg.contents
    if contents is None:
        raise CommandArgError(
            "expected braced word or word without substitutions in argument interpreted"
            " as script"
        )

    # TODO: less hacky way to handle this
    cmd_sub = parser._cmd_sub
    parser._cmd_sub = False
    subtree = parser.parse(contents, pos=arg.contents_pos)
    parser._cmd_sub = cmd_sub

    # TODO: feels like unnecessary hack, but should be fixed with token-based subparse
    subtree.line = arg.line
    subtree.col = arg.col

    subtree.end_pos = arg.end_pos

    return subtree


def arg_count(args, parser):
    # TODO: graceful handling of argsub going into things with recursive parsing.
    # if the argsub happens to be "concrete", we can technically do the right
    # thing (although this should probably be flagged as a readability issue...)
    # otherwise, we should flag that the non-concrete argsub is not okay for
    # these cases. however, I think its not okay-ness doesn't need to be absolute, e.g.
    # I think we could allow:
    #
    #  catch {puts "my script"} {*}$catchopts
    #

    arg_count = 0
    for arg in args:
        if isinstance(arg, ArgExpansion):
            if arg.contents is None:
                return None
            arg_count += len(parser.parse_list(arg.contents))
        else:
            arg_count += 1

    return arg_count


def check_count(command, min=None, max=None):
    def check(args, parser):
        if min is None and max is None:
            return None

        count = arg_count(args, parser)
        if count is None:
            return None

        if min == max and count != min:
            raise CommandArgError(
                f"wrong # of args to {command}: got {count}, expected {min}"
            )

        if min is not None and count < min:
            raise CommandArgError(
                f"not enough args to {command}: got {count}, expected at least {min}"
            )

        if max is not None and count > max:
            raise CommandArgError(
                f"too many args to {command}: got {count}, expected no more than {max}"
            )

        return None

    return check


def subcommands(name, subcommands, default=None):
    def check(args, parser):
        try:
            arg = args[0].contents
        except IndexError:
            arg = None

        if arg in subcommands:
            func = subcommands[arg]
            if func is None:
                return None
            new_args = func(args[1:], parser)
            if new_args is None:
                return None
            return args[0:1] + new_args
        elif default is not None:
            return default(args, parser)
        else:
            if arg is not None:
                msg = f"invalid subcommand for {name}: got {arg}"
            else:
                msg = f"no subcommand provided for {name}"

            raise CommandArgError(
                f"{msg}, expected one of {', '.join(subcommands.keys())}"
            )

    return check


def eval(args, parser, command):
    if len(args) > 1 and any(isinstance(arg, (QuotedWord, BracedWord)) for arg in args):
        # Slightly odd restriction, but our syntax tree doesn't have a great way
        # to handle this case. We require each command argument to correspond to
        # one child node, but multiple quoted or braced word arguments can be
        # combined into a single subcommand when interpreted eval-style. This
        # requirement exists to facilitate style checking, if we had a separate
        # CST for style checks and AST for logical checks we may be able to
        # handle it.

        # TODO: once we have warnings, we could refactor to make this non-fatal
        # and at least parse these arguments as lists to facilitate style
        # checks.

        raise CommandArgError(
            f"unable to parse multiple {command} arguments when one includes a braced"
            " or quoted word"
        )

    eval_args = []
    for arg in args:
        contents = arg.contents
        if contents is None:
            # TODO: flag sort of eval-specific violation? Common patterns will
            # often trigger this, and it seems useful to be able to turn it off
            raise CommandArgError(
                f"{command} received an argument with a substitution, unable to parse"
                " its arguments"
            )
        eval_args.append(contents)

    script = parser.parse(" ".join(eval_args), pos=(args[0].pos))
    script.end_pos = args[-1].end_pos

    return [script]
