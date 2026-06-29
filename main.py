from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from api.tcp.Server import Server
from api.tcp.Client import Client
from api.udp.UDPClient import UDPClient
from api.udp.UDPServer import UDPServer
from api.Packet import Packet
from api.utils.Encryption import Encryption, FileEncryption, SecureEncryption
from api.utils.network import find_servers_local, find_servers_global, ScanStatus
from pathlib import Path
from api.utils.Other import load_public_key, Config, bytes_to_base64, base64_to_bytes
from api.utils.Audio import Audio
import json, threading, random, uuid
import logging
import numpy as np

# basic logging
logging.basicConfig(level=logging.INFO)


pid_uuid = str(uuid.uuid4())
MAX_SIZE_SYNC_PACKET = 64

# default nickname used by background tasks when not set
nickname = ""


connected = []
def backgroud_task(server):
	global connected
	result = find_servers_local(port=1414)
	if result.status == ScanStatus.SUCCESS:
		for srv in result.servers:
			if srv in connected:
				continue
			client = Client(srv, 1414, nickname, MAX_SIZE_SYNC_PACKET)
			server.addInternalClient(client)
			connected.append(srv)

	result = find_servers_global(
		start_ip="1.1.1.1",
		end_ip="255.255.255.255",
		port=1414,
		timeout=2.0
	)
	if result.status == ScanStatus.SUCCESS:
		for srv in result.servers:
			if srv in connected:
				continue
			client = Client(srv, 1414, nickname, MAX_SIZE_SYNC_PACKET)
			server.addInternalClient(client)
			connected.append(srv)


nn_ls = {}
nn_conn = {}

def handle_client_4srv(server, client, addr, th_id):
	global nn_ls
	addr_str = f"{addr[0]}:{addr[1]}"
	try:
		server.init_encrypt(client)
		nn = server.read(client)["name"]
		print(f"Client({nn}) connected!")
		nn_ls[addr_str] = nn
		nn_conn[nn] = client

		while server.isStarted() and (th_id in server._handlers):
			packet = server.read(client)
			if not packet:
				continue

			if packet.get("ping", 0) > 0:
				server.send(client, Packet({"ok": True}))

			elif packet.get("stopsrv"):
				if addr[0] != "127.0.0.1":
					server.send(client, Packet({"ok": False, "error": "You are not host"}))
					continue
				server.send(client, Packet({"ok": True}))
				server.stop()

			elif packet.get("is_online"):
				test_nn = packet.get("is_online")

				if test_nn in nn_conn:
					server.send(client, Packet({"online": True}))

				else:
					if server.getInternalClient() == None:
						server.send(client, Packet({"online": False}))
						continue

					server.getInternalClient().send(Packet({"is_online": test_nn}))
					status = server.getInternalClient().read()
					server.send(client, status)

			elif packet.get("name", False):
				new_name = packet.get("name", "")
				if new_name == "":
					server.send(client, Packet({"ok": False}))
					continue

				old_name = nn
				nn = new_name

				nn_ls[addr_str] = nn
				nn_conn[nn] = client

				# remove old mapping safely
				nn_conn.pop(old_name, None)

				print(f"User change name: {old_name} -> {nn}")
				server.send(client, Packet({"ok": True}))

			elif packet.get("get_address"):
				test_nn = packet.get("get_address")
				if test_nn in nn_conn:
					server.send(client, Packet({"address": nn_conn[test_nn]}))
				else:
					server.send(client, Packet({"address": False}))

			elif packet.get("disconnect"):
				server.stop_handler(th_id)

			else:
				getter = packet.get("to", None)
				content = packet.get("content", None)
				if getter == None:
					continue

				if getter == "server":
					print(f"{nn}: {content}")
					continue

				elif getter == nn:
					continue

				conn = nn_conn.get(getter, None)
				if conn != None:
					server.send(conn, packet)
					continue

				if packet.get("transmit", False):
					continue

				if server.getInternalClient() == None:
					continue

				server.getInternalClient().send(packet)

	except ConnectionError as e:
		logging.debug("ConnectionError in server handler: %s", e)
	except json.JSONDecodeError as e:
		logging.debug("JSON decode error in server handler: %s", e)
	finally:
		name = nn_ls.get(addr_str, None)
		display_name = name if name else "UNKNOWN"
		print(f"{display_name} has been disconnected")

		if name:
			nn_ls.pop(addr_str, None)
			nn_conn.pop(name, None)
		client.close()
		server.stop_handler(th_id)


def handle_client_4clnt(client):
	current_getter = "server"
	while client.isStarted():
		msg = input("msg: ")
		if msg == "/q": client.stop()
		elif msg == "/cc":
			if (client.checkConnection(5)): print("Ok!")
			else: print("Error!")

		elif msg == "/to":
			to = input("Enter recipient's nickname(empty for server): ")
			if to == "":
				current_getter = "server"

			client.send(Packet({"is_online": to}))
			status = client.read()
			print(status)

			if not status.get("online", False):
				print(f"\"{to}\" is not online")
				continue

			current_getter = to

		elif msg == "/read":
			active = True
			print("Q for exit")

			try:
				while active:
					packet = client.read()
					sender, content = packet.get("from", "[unknown]"), packet.get("content", "[ERROR]")

					if content == "Encrypted":
						encript = client.get_encript(current_getter)
						if not encript:
							continue
						nonce = packet.get("encrypted", [])[0]
						ciphertext = packet.get("encrypted", [])[1]

						decripted = encript.decrypt_message(base64_to_bytes(nonce), base64_to_bytes(ciphertext)).decode("utf-8")
						print(f"{sender}: {decripted}")
						continue

					elif content == "/sf":
						encript = client.get_encript(current_getter)
						if not encript:
							continue
						pkt0 = packet
						pkt1 = client.read()
						if pkt0.get("type", None) != "key2file":
							pkt0 = pkt1
							pkt1 = client.read()
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

		elif msg == "/sk": # sync keys
			encript = client.get_encript(current_getter)
			if encript:
				trusted = encript.get_trusted_peer_key(current_getter)
				if trusted:
					print("No verification needed")
					if "x25519_public" in trusted:
						peer_x25519_key = x25519.X25519PublicKey.from_public_bytes(
							trusted["x25519_public"]
						)
						encript.generate_keypair()  # Генерируем новые сессионные ключи
						encript.derive_shared_key(peer_x25519_key)
						print("✅ Защищенный канал восстановлен!")
						continue

			#print("1. for read\n2. for send")
			#mode = int(input("Select mode: "))

			print("Sending key...")
			client.send_key(current_getter)

			print("Reading key packet...")
			client.read_key(current_getter)

		elif msg == "/sf":
			file_path = ""
			try:
				import tkinter as tk
				from tkinter import filedialog
				tk.Tk().withdraw()

				file_path = filedialog.askopenfilename(
					initialdir="/",
					title="Select a file",
					filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
				)

			except Exception as e:
				print(e)
				print("Enter file path manually.")
				file_path = input("File path: ")

			if file_path == "":
				continue

			# get current encryption object
			encript = client.get_encript(current_getter)
			if not encript:
				print("Encryption is not activated")
				continue

			fe = FileEncryption()
			key = fe.getKey()
			ed = fe.encrypt(file_path)
			path_obj = Path(file_path)
			
			with open(str(path_obj.with_suffix(".key")), "wb") as f:
				f.write(key)

			nonce, ciphertext = encript.encrypt_message(key)
			client.transmit(Packet({
				"content": "/sf",
				"type": "key2file",
				"from": client.getUsername(),
				"to": current_getter,
				"encrypted": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
			}))
			status0 = client.read()

			nonce, ciphertext = encript.encrypt_message(path_obj.name.encode("utf-8"))
			client.transmit(Packet({
				"content": "/sf",
				"type": "filedata",
				"from": client.getUsername(),
				"to": current_getter,
				"encrypted": bytes_to_base64(ed),
				"filename": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
			}))
			status1 = client.read()
			print(status0)
			print(status1)

		elif msg == "/voice":
			encript = client.get_encript(current_getter)
			if not encript:
				print("Encryption not initialisated")
				continue

			client.send(Packet({"get_address": current_getter}))
			addr_pkt = client.read()
			target_addr = addr_pkt.get("address")
			if not target_addr:
				print(f"{current_getter} is not online")
				continue

			chunk = 1024
			channels = 1
			port = 4444

			audio = Audio(channels, chunk, 16000)
			udp_s = UDPServer(port, MAX_SIZE_SYNC_PACKET)
			udp_c = UDPClient(target_addr, port, MAX_SIZE_SYNC_PACKET)

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

		else:
			encript = client.get_encript(current_getter)
			if encript:
				nonce, ciphertext = encript.encrypt_message(msg.encode("utf-8"))

				client.transmit(Packet({
					"content": "Encrypted",
					"from": client.getUsername(),
					"to": current_getter,
					"encrypted": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
				}))
			else:
				client.transmit(Packet({
					"content": msg,
					"from": client.getUsername(),
					"to": current_getter
				}))


def main():
	use_cnf = input("use config? (y/n)")
	use_cnf = True if use_cnf.lower() == "y" else False
	config = Config("settings.conf") if use_cnf else None

	if use_cnf:
		config.load()

	mode = None
	if use_cnf:
		mode = config.get("mode", None)
	if mode == None:
		print("Select DM mode:")
		print("0. Server mode")
		print("1. Client mode")
		mode = int(input("Enter mode of DM: "))
		if use_cnf:
			config.set("mode", mode)

	ui_mode = None
	if use_cnf:
		ui_mode = config.get("ui_mode", None)
	if ui_mode == None:
		print("Select UI mode")
		print("0. Start without web UI")
		print("1. Start witch web UI")
		ui_mode = int(input("Enter UI mode: "))
		if use_cnf:
			config.set("ui_mode", ui_mode)
	if use_cnf: config.save()


	def start_webui_thread():
		import uvicorn
		import api.webui as webui
		def _run():
			uvicorn.run(webui.app, host="127.0.0.1", port=8000+random.randint(0, 999), access_log=False)
		t = threading.Thread(target=_run, daemon=True)
		t.start()
		return t

	if mode == 0 and ui_mode == 0:
		server = Server(1414, MAX_SIZE_SYNC_PACKET)
		#bg_thread = threading.Thread(target=backgroud_task, args=(server,), daemon=True)
		#bg_thread.start()

		server.setClientHandler(handle_client_4srv)
		server.start()

	if mode == 1 and ui_mode == 0:
		target = None
		if use_cnf:
			target = config.get("srvAddr", None)
		if not target:
			target = input("Enter target addr: ")
			config.set("srvAddr", target)

		port = None
		if use_cnf:
			port = config.get("port", None)
		if not port:
			port = input("enter port: ")
			port = int(port) if port != "" else 1414
			if use_cnf:
				config.set("port", port)

		nickname = None
		if use_cnf:
			nickname = config.get("nickname", None)
		if not nickname:
			nickname = input("Enter you're name: ")
			if use_cnf:
				config.set("nickname", nickname)
		config.save()

		client = Client(target, port, nickname, MAX_SIZE_SYNC_PACKET)
		client.setThread(handle_client_4clnt)
		client.start()

	# Start web UI option
	if ui_mode == 1:
		start_webui_thread()
		try:
			while True:
				...
		except KeyboardInterrupt:
			pass


if __name__ == "__main__":
	main()