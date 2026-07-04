from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from api.commands.CommandManager import CommandManager
import __main__


class HelpCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        cmdm = __main__.cmdm
        if not isinstance(cmdm, CommandManager):
            print("Non-client environment!")
            return
        cmds = cmdm.getCMDs()
        print("Commands available:")
        for name, cmd in cmds.items():
            print(f"  - /{name}")