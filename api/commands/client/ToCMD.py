from api.Packet import Packet
from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
import __main__


class ToCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        to = input("Enter recipient's nickname(empty for server): ")
        if to == "":
            __main__.current_getter = "server"

        cs.send(Packet({"is_online": to}), True if cs.srv_enc else False)
        status, _enc = cs.read()
        print(status)

        if not status.get("online", False):
            print(f"\"{to}\" is not online")
            return

        __main__.current_getter = to