import threading
import __main__
import numpy as np
from api.Packet import Packet
from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from api.udp.UDPClient import UDPClient
from api.udp.UDPServer import UDPServer
from api.utils.Audio import Audio
from api.utils.Other import base64_to_bytes, bytes_to_base64


class ToCMD(Command):
    def __init__(self):
        pass

    def execute(self, cs: CommandSender):
        encript = cs.get_encript(__main__.current_getter)
        if not encript:
            print("Encryption not initialized")
            return

        cs.send(Packet({"get_address": __main__.current_getter}), True)
        addr_pkt, _enc = cs.read()
        target_addr = addr_pkt.get("address")
        if not target_addr:
            print(f"{__main__.current_getter} is not online")
            return

        chunk = 1024
        channels = 1
        port = 4444

        audio = Audio(channels, chunk, 16000)
        udp_s = UDPServer(port, __main__.MAX_SIZE_SYNC_PACKET)
        udp_c = UDPClient(target_addr, port, __main__.MAX_SIZE_SYNC_PACKET)

        def udp_handle_c(udp_clnt):
            while udp_clnt.isStarted():
                for nda in audio.listen(1):
                    data = nda.tobytes()
                    nonce, ciphertext = encript.encrypt_message(data)
                    to_send = f"{bytes_to_base64(nonce)}:{bytes_to_base64(ciphertext)}".encode("utf-8")
                    udp_clnt.send(target_addr, port, to_send)

        def udp_handle_s(udp_srv, srv_socket):
            while udp_srv.isStarted():
                pkt, addr = udp_srv.read(chunk*channels*2)
                data = pkt.decode("utf-8").split(':')
                nonce, ciphertext = data[0], data[1]
                decoded_data = encript.decrypt_message(base64_to_bytes(nonce), base64_to_bytes(ciphertext)).decode("utf-8")
                to_speak = np.frombuffer(decoded_data, dtype='<u2')
                audio.speak(to_speak)

        udp_c.setThread(udp_handle_c)
        threading.Thread(target=udp_c.start, daemon=True).start()
        udp_s.setClientHandler(udp_handle_s)
        threading.Thread(target=udp_s.start, daemon=True).start()
