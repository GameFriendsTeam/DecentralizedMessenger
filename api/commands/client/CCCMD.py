from api.commands.Command import Command
from api.commands.CommandSender import CommandSender


class CCCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        if (cs.checkConnection(5000)): print("Ok!")
        else: print("Error!")