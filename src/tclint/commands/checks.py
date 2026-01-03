"""Helpers for checking command arguments."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from tclint.syntax_tree import ArgExpansion, BareWord, BracedWord, Node, QuotedWord

# This lets us use Parser in type annotations without introducing a cyclic dependency.
if TYPE_CHECKING:
    from tclint.parser import Parser


class CommandArgError(Exception):
    """Exception raised by command handlers to indicate invalid arguments."""

    pass


def arg_count(args: list[Node], parser: Parser) -> tuple[int, bool]:
    """Returns the number of arguments in args, taking {*} into account.

    If an argument list contains an argument expansion operator that cannot be
    statically expanded, the second return value is True, and the count is the minimum
    possible number of arguments. Otherwise, the return value is False and the count
    reflects the exact number of arguments.

    This function should always be used for validating argument count, rather than
    relying on `len(args)`.
    """

    # TODO: Replace this with or add a similar `expand_args` function that returns an
    # expanded argument list. One tricky thing is we want to handle cases like:
    # - foreach {*}$iters { ...body... }
    # - catch {puts "my script"} {*}$catchopts
    # With something like a list structure we can either forward or reverse index to
    # still parse the body even with an unexpanded {*}.

    # TODO: Add a violation that flags `{*}{a b c}` for rewriting as `a b c`. A future
    # version of tclfmt that allows rewrites that break the syntax tree could do this
    # automatically.

    arg_count = 0
    has_arg_expansion = False
    for arg in args:
        if isinstance(arg, ArgExpansion):
            if arg.contents is None:
                has_arg_expansion = True
                continue
            arg_count += len(parser.parse_list(arg).children)
        else:
            arg_count += 1

    return arg_count, has_arg_expansion


def check_count(command, min=None, max=None):
    def check(args, parser):
        if min is None and max is None:
            return None

        count, has_arg_expansion = arg_count(args, parser)

        if not has_arg_expansion and min == max and count != min:
            raise CommandArgError(
                f"wrong # of args for {command}: got {count}, expected {min}"
            )

        if not has_arg_expansion and min is not None and count < min:
            raise CommandArgError(
                f"not enough args for {command}: got {count}, expected at least {min}"
            )

        if max is not None and count > max:
            raise CommandArgError(
                f"too many args for {command}: got {count}, expected no more than {max}"
            )

        return None

    return check


def eval(args: list[Node], parser: Parser, command: str) -> list[Node]:
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
    command: str,
    args: list[Node],
    parser: Parser,
    command_spec: Callable | dict | None,
) -> Optional[list[Node]]:
    if command_spec is None:
        return None

    if isinstance(command_spec, dict):
        return check_arg_spec(command, args, parser, command_spec)

    return command_spec(args, parser)


def _positional_has_type(type: str, arg_spec: dict, indices: list[int]) -> bool:
    return any([arg_spec["positionals"][i]["value"]["type"] == type for i in indices])


def check_arg_spec(
    command: str, args: list[Node], parser: Parser, arg_spec: dict
) -> Optional[list[Node]]:
    if "subcommands" in arg_spec:
        return dispatch_subcommands(command, args, parser, arg_spec["subcommands"])

    switches = arg_spec["switches"]
    args_allowed = set(switches)
    args_required = {switch for switch in switches if switches[switch]["required"]}

    # indices into args
    positional_args: list[int] = []
    arg_i = 0

    if not switches:
        positional_args = list(range(len(args)))
        arg_i = len(args)

    while arg_i < len(args):
        arg = args[arg_i]
        arg_i += 1

        # To facilitate better error messages, we expect that switches are always
        # specified as BareWords that start with "-" or ">". This lets us throw an
        # error when a switch-like thing doesn't match any supported arguments,
        # rather than counting it towards the positional arguments (which usually
        # ends up in a vague "too many arguments" error). To make tclint interpret a
        # switch-like word as a positional argument, users should wrap it in "", and
        # any switches should be BareWords.
        contents = arg.contents
        if not (isinstance(arg, BareWord) and contents and contents[0] in {"-", ">"}):
            positional_args.append(arg_i - 1)
            continue

        # TODO check required arguments
        if contents in args_allowed:
            if switches[contents]["value"]:
                arg_i += 1
                if arg_i > len(args):
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

    positionals = [args[i] for i in positional_args]
    mapping = map_positionals(positionals, arg_spec["positionals"], command)
    args = list(args)
    for arg_i, map_to_spec in zip(positional_args, mapping):
        if _positional_has_type("script", arg_spec, map_to_spec):
            args[arg_i] = parser.parse_script(args[arg_i])
        elif _positional_has_type("expression", arg_spec, map_to_spec):
            args[arg_i] = parser.parse_expression(args[arg_i])

    return args


def dispatch_subcommands(
    command: str, args: list[Node], parser: Parser, spec: dict
) -> Optional[list[Node]]:
    try:
        subcommand = args[0].contents
    except IndexError:
        subcommand = None

    if subcommand in spec:
        new_args = check_command(
            f"{command} {subcommand}", args[1:], parser, spec[subcommand]
        )
        if new_args is None:
            return new_args
        return args[0:1] + new_args

    if "" in spec:
        return check_command(command, args, parser, spec[""])

    if subcommand is not None:
        msg = f"invalid subcommand for {command}: got {subcommand}"
    else:
        msg = f"no subcommand provided for {command}"

    raise CommandArgError(f"{msg}, expected one of {', '.join(spec.keys())}")


def map_positionals(
    args: list[Node], spec: list[dict], command_name: str
) -> list[list[int]]:
    """Maps a list of nodes representing positional command arguments to the specific
    positional arguments of a command. spec represents the "positionals" entry of the
    spec for the given command.

    The return value is a list whose entries correspond one-to-one to the entries in
    `args`. Each item in the return value is a list of indices into `spec`, indicating
    which argument(s) in the spec the corresponding argument maps to.

    A given index into `spec` may appear multiple times in the list (e.g. if it's a
    variadic argument), and a list may contain more than one index for the mapping of an
    arg expansion.

    If the arguments do not map correctly to the spec, this function raises
    CommandArgError.

    Given a set of args and a spec, there may be multiple possible mappings. This
    function will return some mapping if one exists.

    The `command_name` argument is used to generate descriptive error messages.
    """

    if len(args) == len(spec):
        # Self explanatory: a 1:1 match in argument count should be a legal mapping.
        return [[i] for i in range(len(args))]

    mapping: list[list[int]] = []
    i = 0
    if len(args) > len(spec):
        # If there are more arguments than specified positionals, we map every argument
        # greedily and assign the extra # of arguments to the first variadic we find.
        extra = len(args) - len(spec)
        for arg in args:
            if i >= len(spec):
                # We never found a variadic to save us, raise an error.
                raise CommandArgError(
                    f"too many arguments for {command_name}: got {len(args)}, expected"
                    f" no more than {len(spec)}"
                )

            mapping.append([i])
            if spec[i]["value"]["type"] == "variadic" and extra > 0:
                extra -= 1
            else:
                i += 1

        return mapping

    required = []
    for argspec in spec:
        if argspec["required"]:
            required.append(argspec["name"])
    num_required = len(required)

    if len(args) < num_required:
        # If there are fewer arguments than required positionals, we map only required
        # arguments and expand the first arg expansion we find to account for what's
        # missing.
        missing = num_required - len(args)
        for arg in args:
            while not spec[i]["required"]:
                i += 1

            mapping.append([i])
            i += 1

            if isinstance(arg, ArgExpansion):
                # Map missing arguments.
                while missing > 0:
                    if spec[i]["required"]:
                        mapping[-1] += [i]
                        missing -= 1
                    i += 1

        if missing > 0:
            missing_names = ", ".join(required[-missing:])
            raise CommandArgError(
                f"missing required argument{'s' if missing > 1 else ''} for"
                f" {command_name}: {missing_names}"
            )

        return mapping

    optionals = len(args) - num_required
    for arg in args:
        # If our argument count falls somewhere in between the required and total
        # specified numbers of positionals, we map all required arguments and map as
        # many optionals as needed (as we find them).
        if not spec[i]["required"] and optionals > 0:
            mapping.append([i])
            i += 1
            optionals -= 1
            continue

        while not spec[i]["required"]:
            i += 1

        mapping.append([i])
        i += 1

    return mapping
