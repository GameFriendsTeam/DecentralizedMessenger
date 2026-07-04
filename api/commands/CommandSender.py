from api.Packet import Packet
from api.utils.Encryption import SecureEncryption


class CommandSender:
    def read(self) -> tuple[Packet, bool]:
        pass

    def send(self, packet: Packet, encrypt: bool = False):
        pass

    def stop():
        pass

    def transmit(self, packet: Packet, encrypt: bool = False):
        pass

    def get_encript(self, to: str) -> SecureEncryption:
        pass

    def checkConnection(self, timeout: int) -> bool:
            pass