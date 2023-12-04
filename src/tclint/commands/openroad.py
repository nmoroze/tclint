from tclint.commands.parse_help import parse_help_file
from tclint.commands.utils import CommandArgError
from tclint.syntax_tree import ArgExpansion

_commands = parse_help_file('/Users/noah/Code/tclint/openroad-help.txt')

def check_arg_spec(command, arg_spec):
    def check(args, parser):
        if command in {'estimate_parasitics', 'check_antennas'}:
            return None

        args_allowed = set(arg_spec.keys())
        # print(command)
        # print(arg_spec)
        positional_args_allowed = arg_spec[""]["value"]

        has_argsub = any([isinstance(a, ArgExpansion) for a in args])

        args = list(args)
        while len(args) > 0:
            arg = args.pop(0)
            contents = arg.contents
            if contents is None:
                positional_args_allowed -= 1
                continue

            if contents in args_allowed:
                for _ in range(arg_spec[contents]['value']):
                    # pop off however many values required
                    args.pop(0)
                    # TODO: error check
                args_allowed.remove(contents)
            else:
                if contents in arg_spec:
                    raise CommandArgError(f"duplicate argument {contents}")
                positional_args_allowed -= 1

        if not has_argsub and positional_args_allowed < 0:
            raise CommandArgError("too many arguments")


        return None

    return check

commands = {command: check_arg_spec(command, arg_spec) for command, arg_spec in _commands.items()}
