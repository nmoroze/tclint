import importlib

def get_commands(plugins):
    commands = {}

    for command_set in plugins:
        mod = importlib.import_module(f'tclint.commands.{command_set}')
        commands.update(mod.commands)

    return commands
