from api.commands.Command import Command
from api.commands.CommandSender import CommandSender


class QCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        cs.stop()