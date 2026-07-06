from api.commands.CommandManager import CommandManager
from api.ctp.Server import Server
from api.ctp.Client import Client
from api.Packet import Packet
from api.utils.network import find_servers_local, find_servers_global, ScanStatus
from api.utils.Other import get_all_commands, Config, bytes_to_base64, get_async_ctx, is_valid_ip, run_async_ctx
import json, threading, random, uuid
import logging

# basic logging
logging.basicConfig(level=logging.INFO)


pid_uuid = str(uuid.uuid4())
MAX_SIZE_SYNC_PACKET = 256


nn_ls = {}
nn_conn = {}

def handle_client_4srv(server: Server, client, addr, th_id):
	global nn_ls
	addr_str = f"{addr[0]}:{addr[1]}"
	try:
		server.sinit_encrypt(client)
		nn = server.sread(client)[0]["name"]
		logging.info(f"Client({nn}) connected!")
		nn_ls[addr_str] = nn
		nn_conn[nn] = client

		while server.isStarted() and (th_id in server._handlers):
			packet, _enc = server.sread(client)
			if not packet:
				continue

			if packet.get("ping", 0) > 0:
				server.ssend(client, Packet({"ok": True}), _enc)

			elif packet.get("stopsrv"):
				if addr[0] != "127.0.0.1":
					server.ssend(client, Packet({"ok": False, "error": "You are not host"}), _enc)
					continue
				server.ssend(client, Packet({"ok": True}), _enc)
				server.stop()

			elif packet.get("is_online"):
				test_nn = packet.get("is_online")

				if test_nn in nn_conn:
					server.ssend(client, Packet({"online": True}), _enc)

				else:
					if server.getInternalClient() == None:
						server.ssend(client, Packet({"online": False}), _enc)
						continue

					server.getInternalClient().send(Packet({"is_online": test_nn}), _enc)
					status, _enc = server.getInternalClient().read()
					server.ssend(client, status, _enc)

			elif packet.get("name", False):
				new_name = packet.get("name", "")
				if new_name == "":
					server.ssend(client, Packet({"ok": False}), _enc)
					continue

				old_name = nn
				nn = new_name

				nn_ls[addr_str] = nn
				nn_conn[nn] = client

				# remove old mapping safely
				nn_conn.pop(old_name, None)

				logging.info(f"User change name: {old_name} -> {nn}")
				server.ssend(client, Packet({"ok": True}), _enc)

			elif packet.get("get_address"):
				test_nn = packet.get("get_address")
				if test_nn in nn_conn:
					server.ssend(client, Packet({"address": nn_conn[test_nn]}), _enc)
				else:
					server.ssend(client, Packet({"address": False}), _enc)

			elif packet.get("disconnect"):
				server.stop_handler(th_id)

			else:
				getter = packet.get("to", None)
				content = packet.get("content", None)
				if getter == None:
					continue

				if getter == "server":
					logging.info(f"{nn}: {content}")
					continue

				elif getter == nn:
					continue

				conn = nn_conn.get(getter, None)
				has_enc = True if server._encryptes.get(conn, None) else False
				if conn != None:
					server.ssend(conn, packet, has_enc)
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
		logging.info(f"{display_name} has been disconnected")

		if name:
			nn_ls.pop(addr_str, None)
			nn_conn.pop(name, None)
		# client.close()
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
				logging.info("Command doesn't exists!")

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


def main(args):

	use_cnf = not args.no_use_config
	mode = 0 if args.server else 1
	ui_mode = 1 if args.webui else 0
	config = Config("settings.conf") if use_cnf else None

	if use_cnf:
		config.load()
		conf_mode = config.get("mode", None)
		conf_ui = config.get("ui_mode", None)
		if conf_mode is not None:
			mode = conf_mode
		else:
			config.set("mode", mode)
		if conf_ui is not None:
			ui_mode = conf_ui
		else:
			config.set("ui_mode", ui_mode)


	def start_webui_thread():
		import uvicorn
		import api.webui as webui
		def _run(): uvicorn.run(webui.app, host="127.0.0.1", port=8000+random.randint(0, 999), access_log=False)
		threading.Thread(target=_run, daemon=True).start()


	if mode == 0 and ui_mode == 0:
		async def start_server():
			global handle_client_4srv
			server = await Server.create(1414, MAX_SIZE_SYNC_PACKET)

			server.setClientHandler(handle_client_4srv)
			await server.start()

		aloop = get_async_ctx(__name__)
		run_async_ctx(aloop, start_server(), timeout=None)

	if mode == 1 and ui_mode == 0:
		addr = None
		port = None
		if use_cnf:
			addr = config.get("address", None)
			port = config.get("port", None)
		if not addr or not port:
			try:
				raw = input("Enter target (addr:port): ").split(":")
				addr, port = raw[0], int(raw[1])
			except IndexError:
				logging.info("Invalid input format. Please enter in the format 'address:port'.")
				return

			if not is_valid_ip(addr):
				logging.info("Invalid IP address")
				return
			if use_cnf:
				config.set("address", addr)
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

		client = Client(addr, port, nickname, MAX_SIZE_SYNC_PACKET)
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
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--no-use-config", action="store_true", help="Don't use config file")
	parser.add_argument("--server", "-s", action="store_true", help="Start in server mode")
	parser.add_argument("--webui", "-w", action="store_true", help="Start with web UI")
	args = parser.parse_args()
	main(args)