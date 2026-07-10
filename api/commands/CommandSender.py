from api.Packet import Packet
from api.utils.Encryption import SecureEncryption


class CommandSender:
    def read(self, timeout: int = 6) -> tuple[Packet, bool]:
        pass

    def send(self, packet: Packet, encrypt: bool = False):
        pass

    def stop(self):
        pass

    def transmit(self, packet: Packet, encrypt: bool = False):
        pass

    def get_encript(self, to: str) -> SecureEncryption:
        pass

    def checkConnection(self, timeout: int) -> bool:
            pass
    
    def connectionIsSecure(self) -> bool:
        return bool()

    def send_key(self, to: str):
        pass

    def read_key(self, sender: str, timeout: int = 6):
        pass