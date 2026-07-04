from api.Packet import Packet
from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from cryptography.hazmat.primitives.asymmetric import x25519
import __main__


class ToCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        encript = cs.get_encript(__main__.current_getter)
        if encript:
            trusted = encript.get_trusted_peer_key(__main__.current_getter)
            if trusted:
                print("No verification needed")
                if "x25519_public" in trusted:
                    peer_x25519_key = x25519.X25519PublicKey.from_public_bytes(
                        trusted["x25519_public"]
                    )
                    encript.generate_keypair()
                    encript.derive_shared_key(peer_x25519_key)
                    print("✅ Защищенный канал восстановлен!")
                    return

        print("Sending key...")
        cs.send_key(__main__.current_getter)

        print("Reading key packet...")
        cs.read_key(__main__.current_getter)