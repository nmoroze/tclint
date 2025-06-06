"""Helpers for checking command arguments."""

from collections.abc import Callable
from typing import List, Optional, Union

from tclint.syntax_tree import ArgExpansion, QuotedWord, BracedWord, BareWord, Node


class CommandArgError(Exception):
    pass


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
    has_arg_expansion = False
    for arg in args:
        if isinstance(arg, ArgExpansion):
            if arg.contents is None:
                has_arg_expansion = True
                continue
            arg_count += len(parser.parse_list(arg.contents))
        else:
            arg_count += 1

    return arg_count, has_arg_expansion


def check_count(command, min=None, max=None, args_name="args"):
    def check(args, parser):
        if min is None and max is None:
            return None

        count, has_arg_expansion = arg_count(args, parser)

        if not has_arg_expansion and min == max and count != min:
            raise CommandArgError(
                f"wrong # of {args_name} for {command}: got {count}, expected {min}"
            )

        if not has_arg_expansion and min is not None and count < min:
            raise CommandArgError(
                f"not enough {args_name} for {command}: got {count}, expected at least"
                f" {min}"
            )

        if max is not None and count > max:
            raise CommandArgError(
                f"too many {args_name} for {command}: got {count}, expected no more"
                f" than {max}"
            )

        return None

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

        raise CommandArgError(
            f"unable to parse multiple {command} arguments when one includes a braced"
            " or quoted word"
        )

    # Construct the body of the eval taking whitespace into account to ensure we get
    # style checking.

    eval_script = ""
    prev_arg_end_pos = None
    for arg in args:
        contents = arg.contents
        if contents is None:
            # TODO: flag sort of eval-specific violation? Common patterns will
            # often trigger this, and it seems useful to be able to turn it off
            raise CommandArgError(
                f"{command} received an argument with a substitution, unable to parse"
                " its arguments"
            )

        if prev_arg_end_pos is not None:
            if prev_arg_end_pos[0] != arg.line:
                # If we have multiple args on the same line, we know there must be a
                # backslash newline. Add it so the parsing works.
                eval_script += "\\\n" * (arg.line - prev_arg_end_pos[0])
                eval_script += " " * (arg.col - 1)
            else:
                eval_script += " " * (arg.col - prev_arg_end_pos[1])
        eval_script += contents

        prev_arg_end_pos = arg.end_pos

    script = parser.parse(eval_script, pos=(args[0].pos))
    script.end_pos = args[-1].end_pos

    return [script]


def check_command(
    command: str, args: List[Node], parser, command_spec: Union[Callable, dict, None]
) -> Optional[List[Node]]:
    if command_spec is None:
        return None

    if isinstance(command_spec, dict):
        return check_arg_spec(command, args, parser, command_spec)

    return command_spec(args, parser)


def check_arg_spec(
    command: str, args: List[Node], parser, arg_spec: dict
) -> Optional[List[Node]]:
    if "subcommands" in arg_spec:
        subcommands = arg_spec["subcommands"]
        try:
            subcommand = args[0].contents
        except IndexError:
            subcommand = None

        if subcommand in subcommands:
            new_args = check_command(
                f"{command} {subcommand}", args[1:], parser, subcommands[subcommand]
            )
            if new_args is None:
                return new_args
            return args[0:1] + new_args

        if "" in subcommands:
            return check_command(command, args, parser, subcommands[""])

        if subcommand is not None:
            msg = f"invalid subcommand for {command}: got {subcommand}"
        else:
            msg = f"no subcommand provided for {command}"

        raise CommandArgError(f"{msg}, expected one of {', '.join(subcommands.keys())}")

    switches = arg_spec["switches"]
    args_allowed = set(switches)
    args_required = {switch for switch in switches if switches[switch]["required"]}
    positional_args = []

    args = list(args)
    while len(args) > 0:
        arg = args.pop(0)

        # To facilitate better error messages, we expect that switches are always
        # specified as BareWords that start with "-" or ">". This lets us throw an
        # error when a switch-like thing doesn't match any supported arguments,
        # rather than counting it towards the positional arguments (which usually
        # ends up in a vague "too many arguments" error). To make tclint interpret a
        # switch-like word as a positional argument, users should wrap it in "", and
        # any switches should be BareWords.
        contents = arg.contents
        if not (isinstance(arg, BareWord) and contents and contents[0] in {"-", ">"}):
            positional_args.append(arg)
            continue

        # TODO check required arguments
        if contents in args_allowed:
            if switches[contents]["value"]:
                try:
                    args.pop(0)
                except IndexError:
                    raise CommandArgError(
                        f"invalid arguments for {command}: expected value after"
                        f" {contents}"
                    )
            if not switches[contents]["repeated"]:
                args_allowed.remove(contents)
            if contents in args_required:
                args_required.remove(contents)
        elif contents in arg_spec:
            raise CommandArgError(f"duplicate argument for {command}: {contents}")
        else:
            prefix_matches = []
            for switch in switches:
                if switch.startswith(contents):
                    prefix_matches.append(switch)

            if len(prefix_matches) == 1:
                raise CommandArgError(
                    f"shortened argument for {command}: expand {contents} to"
                    f" {prefix_matches[0]}"
                )

            if len(prefix_matches) > 1:
                raise CommandArgError(
                    f"ambiguous argument for {command}: {contents} could be any of"
                    f" {', '.join(prefix_matches)}"
                )

            raise CommandArgError(f"unrecognized argument for {command}: {contents}")

    if len(args_required) > 1:
        raise CommandArgError(
            f"missing required arguments for {command}: {', '.join(args_required)}"
        )
    elif len(args_required) == 1:
        raise CommandArgError(
            f"missing required argument for {command}: {args_required.pop()}"
        )

    min_positionals = 0
    max_positionals: Optional[int] = 0
    for positional in arg_spec["positionals"]:
        if positional["value"]["type"] == "variadic":
            max_positionals = None

        if positional["required"]:
            min_positionals += 1
        if max_positionals is not None:
            max_positionals += 1

    check = check_count(
        command,
        min=min_positionals,
        max=max_positionals,
        args_name="positional args",
    )
    check(positional_args, None)

    return None
