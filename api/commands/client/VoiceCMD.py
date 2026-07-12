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
from api.hp.UDP import get_own_address, punch, parse_addr


class VoiceCMD(Command):
    def __init__(self):
        ...

    def execute(self, cs: CommandSender):
        encript = cs.get_encript(__main__.current_getter)
        if not encript:
            print("Encryption not initialized")
            return

        chunk = 1024
        channels = 1
        port = 4444

        audio = Audio(channels, chunk, 16000)

        try:
            addr_data = input("Enter address of server with support UDP punch hole (format: ipV4:port): ").split(":")
            rhost, rport = addr_data[0], int(addr_data[1])
        except KeyboardInterrupt:
            print("User cancel enter")
            return
        except Exception as e:
            print(e)
            return

        you = get_own_address(rhost, rport, port)
        you = f"{you[0]}:{you[1]}"

        encript = cs.get_encript(__main__.current_getter)

        nonce, chipertext = encript.encrypt_message(you.encode("utf-8"))
        cs.transmit(Packet({"type": "my_addr", "my_addr": [bytes_to_base64(nonce), bytes_to_base64(chipertext)], "to": __main__.current_getter}), True)

        peer_pkt, _enc = cs.wait_packet("my_addr", timeout=5.0)
        nonce, chipertext = peer_pkt.get("my_addr", None)[0], peer_pkt.get("my_addr", None)[1]
        dec_addr = encript.decrypt_message(base64_to_bytes(nonce), base64_to_bytes(chipertext)).decode("utf-8")
        target_addr, peer_port = parse_addr(dec_addr)

        if not target_addr:
            print("Peer addr not gotten")
            return

        udp_s = UDPServer(port, __main__.MAX_SIZE_SYNC_PACKET)
        udp_c = UDPClient(target_addr, peer_port, __main__.MAX_SIZE_SYNC_PACKET)

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
