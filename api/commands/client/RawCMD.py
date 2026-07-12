import json
from typing import Optional
from api.Packet import Packet
from api.commands.Command import Command
from api.commands.CommandSender import CommandSender


class RawCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        print("Send a self-written packet in JSON (Empty line for skip)")
        raw = input(":")
        data: Optional[dict | list] = None
        try:
            data: dict | list = json.loads(raw)
        except json.JSONDecodeError:
            print("Input JSON format is not correct!")
        if not data:
            return
        if isinstance(data, dict):
            cs.send(Packet(data), True)
        else:
            cs.send(Packet({"type": "raw", "data": data}), True)
        result, _enc = cs.wait_packet("status", 5.0)
        data = json.dumps(result.getAll())
        print(data, f"Is encrypted: {_enc}", sep="\n")