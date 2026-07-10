from api.commands.Command import Command
from api.commands.CommandSender import CommandSender


class CCCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        status, time = cs.checkConnection(5000)
        if (status): print("Ok! In ", int(time*1000), "ms",sep="")
        else: print("Error!")