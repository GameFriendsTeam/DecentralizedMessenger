from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from api.utils.Encryption import FileEncryption
from api.utils.Other import base64_to_bytes
import __main__


class ReadCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        active = True
        print("Q for exit")

        try:
            while active:
                packet, _enc = cs.read(None)
                if not packet:
                    continue
                sender, content = packet.get("from", "[unknown]"), packet.get("content", "[ERROR]")

                if content == "Encrypted":
                    encript = cs.get_encript(__main__.current_getter)
                    if not encript:
                        continue
                    nonce = packet.get("encrypted", [])[0]
                    ciphertext = packet.get("encrypted", [])[1]

                    decripted = encript.decrypt_message(base64_to_bytes(nonce), base64_to_bytes(ciphertext)).decode("utf-8")
                    print(f"{sender}: {decripted}")
                    continue

                elif content == "/sf":
                    encript = cs.get_encript(__main__.current_getter)
                    if not encript:
                        continue
                    pkt0 = packet
                    pkt1, _enc = cs.read(None)
                    if pkt0.get("type", None) != "key2file":
                        pkt0 = pkt1
                        pkt1, _enc = cs.read(None)
                    if pkt1.get("type", None) != "filedata":
                        print("Incorrect data")
                        continue

                    encrypted = pkt0.get("encrypted")
                    key = bytes(encript.decrypt_message(base64_to_bytes(encrypted[0]), base64_to_bytes(encrypted[1])))

                    fe = FileEncryption(key)
                    decrypted = fe.decrypt(base64_to_bytes(pkt1.get("encrypted")))

                    name_enc = pkt1.get("filename")
                    filename = encript.decrypt_message(base64_to_bytes(name_enc[0]), base64_to_bytes(name_enc[1])).decode("utf-8")

                    with open(filename, "wb") as f:
                        f.write(decrypted)
                    continue

                print(f"{sender}: {content}")
        except KeyboardInterrupt:
            active = False
