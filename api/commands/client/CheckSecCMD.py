from api.commands.Command import Command
from api.commands.CommandSender import CommandSender
from api.Packet import Packet
import __main__
import logging

from api.utils.Other import bytes_to_base64


class CheckSecCMD(Command):
	def __init__(self):
		pass

	def execute(self, cs: CommandSender):
		first_check = cs.connectionIsSecure()

		cs.send(Packet({"ping": 5}), first_check)
		okay, enc = cs.read()
		second_check = enc
		third_check = None
		if __main__.current_getter != "server":
			third_check = cs.get_encript(__main__.current_getter)

		text0 = f"Client<->Server connection is secure: {'yes' if first_check else 'no'}"
		text1 = f"Encryption can be used: {'yes' if second_check else 'no'}"
		text2 = f"Client<->Client connection is secure: {'yes' if third_check else 'no'}"

		if first_check:
			logging.info(text0)
		else:
			logging.warning(text0)
		if second_check:
			logging.info(text1)
		else:
			logging.warning(text1)

		if __main__.current_getter != "server":
			peer_is_not_sus = False

			enc = cs.get_encript(__main__.current_getter)
			if enc:
				my_x25519_pub = enc.serialize_x25519_public()
				my_ed25519_pub = enc.serialize_ed25519_public()
				cs.send(Packet({
					"type": "key_check",
					"x25519_pub": bytes_to_base64(my_x25519_pub),
					"ed25519_pub": bytes_to_base64(my_ed25519_pub)
				}))
				input("Press Enter to continue...")
				peer_key_pkt, _ = cs.read()
				peer_x25519_pub = bytes_to_base64(peer_key_pkt.get("x25519_pub"))
				peer_ed25519_pub = bytes_to_base64(peer_key_pkt.get("ed25519_pub"))
				trusted_ed25519_key = enc.get_trusted_peer_key(__main__.current_getter)[0]
				trusted_x25519_key = enc.get_trusted_peer_key(__main__.current_getter)[1]

				if peer_ed25519_pub != bytes_to_base64(trusted_ed25519_key) or peer_x25519_pub != bytes_to_base64(trusted_x25519_key):
					peer_is_not_sus = True
				yes_str = "yes" if not peer_is_not_sus else "sus"
				text2 = f"Client<->Client connection is secure: {yes_str}"

			if not peer_is_not_sus:
				logging.info(text2)
			else:
				logging.warning(text2)
		else:
			logging.warning("Client<->Client connection is secure: unknown (no peer selected)")