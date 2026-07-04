from typing import Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from api.commands.CommandManager import CommandManager
from api.tcp.Server import Server
from api.tcp.Client import Client
from api.udp.UDPClient import UDPClient
from api.udp.UDPServer import UDPServer
from api.Packet import Packet
from api.utils.Encryption import Encryption, FileEncryption, SecureEncryption
from api.utils.network import find_servers_local, find_servers_global, ScanStatus
from pathlib import Path
from api.utils.Other import get_all_commands, load_public_key, Config, bytes_to_base64, base64_to_bytes
from api.utils.Audio import Audio
import json, threading, random, uuid
import logging
import numpy as np

# basic logging
logging.basicConfig(level=logging.INFO)


pid_uuid = str(uuid.uuid4())
MAX_SIZE_SYNC_PACKET = 256

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

def handle_client_4srv(server: Server, client, addr, th_id):
	global nn_ls
	addr_str = f"{addr[0]}:{addr[1]}"
	try:
		server.init_encrypt(client)
		nn = server.read(client)[0]["name"]
		print(f"Client({nn}) connected!")
		nn_ls[addr_str] = nn
		nn_conn[nn] = client

		while server.isStarted() and (th_id in server._handlers):
			packet, _enc = server.read(client)
			if not packet:
				continue

			if packet.get("ping", 0) > 0:
				server.send(client, Packet({"ok": True}), _enc)

			elif packet.get("stopsrv"):
				if addr[0] != "127.0.0.1":
					server.send(client, Packet({"ok": False, "error": "You are not host"}))
					continue
				server.send(client, Packet({"ok": True}), _enc)
				server.stop()

			elif packet.get("is_online"):
				test_nn = packet.get("is_online")

				if test_nn in nn_conn:
					server.send(client, Packet({"online": True}), _enc)

				else:
					if server.getInternalClient() == None:
						server.send(client, Packet({"online": False}), _enc)
						continue

					server.getInternalClient().send(Packet({"is_online": test_nn}), _enc)
					status, _enc = server.getInternalClient().read()
					server.send(client, status, _enc)

			elif packet.get("name", False):
				new_name = packet.get("name", "")
				if new_name == "":
					server.send(client, Packet({"ok": False}), _enc)
					continue

				old_name = nn
				nn = new_name

				nn_ls[addr_str] = nn
				nn_conn[nn] = client

				# remove old mapping safely
				nn_conn.pop(old_name, None)

				print(f"User change name: {old_name} -> {nn}")
				server.send(client, Packet({"ok": True}), _enc)

			elif packet.get("get_address"):
				test_nn = packet.get("get_address")
				if test_nn in nn_conn:
					server.send(client, Packet({"address": nn_conn[test_nn]}), _enc)
				else:
					server.send(client, Packet({"address": False}), _enc)

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
				has_enc = True if server._encryptes.get(conn, None) else False
				if conn != None:
					server.send(conn, packet, has_enc)
					continue

				if packet.get("transmit", False):
					continue

				if server.getInternalClient() == None:
					continue

				server.getInternalClient().send(packet, True)

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

cmdm = None
current_getter = "server"
def handle_client_4clnt(client: Client):
	global cmdm
	from api.commands.client._HelpCMD import HelpCMD

	cmdm = CommandManager()
	cmdm.registerCMDs(get_all_commands())
	cmdm.registerCMD("help", HelpCMD())

	while client.isStarted():
		msg = input("msg: ")
		if msg.startswith("/"):
			cmd = msg.lower().replace("/", "").split(" ")[0]
			mb_cmd = cmdm.getCMD(cmd, None)
			if mb_cmd:
				mb_cmd.execute(client)
			else:
				print("Command doesn't exists!")

		else:
			encript = client.get_encript(current_getter)
			if encript:
				nonce, ciphertext = encript.encrypt_message(msg.encode("utf-8"))

				client.transmit(Packet({
					"content": "Encrypted",
					"from": client.getUsername(),
					"to": current_getter,
					"encrypted": [bytes_to_base64(nonce), bytes_to_base64(ciphertext)]
				}), True)
			else:
				client.transmit(Packet({
					"content": msg,
					"from": client.getUsername(),
					"to": current_getter
				}), True)


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
			if use_cnf:
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
		if use_cnf:
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