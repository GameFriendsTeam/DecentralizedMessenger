import asyncio
import sys
from api.commands.CommandManager import CommandManager
from api.ctp.Server import Server
from api.ctp.Client import Client
from api.Packet import Packet
from api.protocol.stream import Stream
from api.utils.network import find_servers_local, find_servers_global, ScanStatus
from api.utils.Other import get_all_commands, Config, bytes_to_base64, get_async_ctx, is_valid_ip, run_async_ctx
from api.hp.Server import handle_client
import json, threading, random, uuid
import logging
import time


#if sys.platform == 'win32':
#	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# basic logging
logging.basicConfig(level=logging.INFO)


pid_uuid = str(uuid.uuid4())
MAX_SIZE_SYNC_PACKET = 128


nn_ls = {}
nn_conn = {}
th_ids = {}
loop = asyncio.SelectorEventLoop()
asyncio.set_event_loop(loop)


srv_disable_encryption = False
def handle_client_4srv(server: Server, client: Stream, addr, th_id):
	global nn_ls, nn_conn, th_ids
	addr_str = f"{addr[0]}:{addr[1]}"
	try:
		suffix = ""
		if not srv_disable_encryption:
			server.sinit_encrypt(client)
		else:
			server.ssend(client, Packet({"no_encryption": True}))
		nn = server.sread(client)[0]["name"]
		if nn in nn_conn:
			nn_addr = nn_ls[nn]
			logging.warning(f"Client {nn} has been connected already. Pinging {nn_addr} connection...")
			try:
				pkt, _enc = server.sread(nn_conn.get(nn), 2)
				if not pkt:
					raise Exception("")
				client.close()
				server.stop_handler(th_id)
			except:
				logging.warning(F"Connection of {nn_addr} out of date")
				nn_ls.pop(nn, None)
				run_async_ctx(loop, nn_conn.get(nn).close())
				nn_conn.pop(nn, None)
				th_ids.pop(nn)
				logging.info(f"Disconnected {nn_addr}")
				suffix = "(Reconnect) "
				
		logging.info(f"{suffix}Client({nn}) connected!")
		nn_ls[nn] = addr_str
		nn_conn[nn] = client
		th_ids[nn] = th_id
		logging.info("Sending confirmation...")
		server.ssend(client, Packet({"ok": True}), not srv_disable_encryption)
		logging.info("Waiting for ready signal...")
		status, _enc = server.sread(client)
		logging.info(f"Ready signal received. {status}")

		while server.isStarted() and (th_id in server._handlers) and (nn in nn_conn):
			packet, _enc = server.sread(client)
			if not packet:
				continue

			if ping := packet.get("ping", 0):
				client_ts = packet.get("timestamp", 0)
				server_ts = time.time()
				if server_ts-client_ts > ping*1000:
					server.ssend(client, Packet({"ok": False}), _enc and not srv_disable_encryption)
					continue
				server.ssend(client, Packet({"ok": True}), _enc and not srv_disable_encryption)
				ping = (server_ts-client_ts)*1000
				logging.info(f"Server gotten ping packet. Packet latency: {str(int(ping))}ms")

			elif packet.get("stopsrv"):
				if addr[0] != "127.0.0.1":
					server.ssend(client, Packet({"ok": False, "error": "You are not host"}), _enc and not srv_disable_encryption)
					continue
				logging.info("Stopping server...")
				server.ssend(client, Packet({"ok": True}), _enc and not srv_disable_encryption)
				server.stop()

			elif packet.get("is_online"):
				test_nn = packet.get("is_online")

				if test_nn in nn_conn:
					server.ssend(client, Packet({"online": True}), _enc and not srv_disable_encryption)

				else:
					if server.getInternalClient() == None:
						server.ssend(client, Packet({"online": False}), _enc and not srv_disable_encryption)
						continue

					server.getInternalClient().send(Packet({"is_online": test_nn}), _enc and not srv_disable_encryption)
					status, _enc = server.getInternalClient().read()
					server.ssend(client, status, _enc and not srv_disable_encryption)

			elif packet.get("name", False):
				new_name = packet.get("name", "")
				if new_name == "":
					server.ssend(client, Packet({"ok": False}), _enc and not srv_disable_encryption)
					continue

				old_name = nn
				nn = new_name

				nn_ls[nn] = addr_str
				nn_conn[nn] = client

				# remove old mapping safely
				nn_conn.pop(old_name, None)

				logging.info(f"User change name: {old_name} -> {nn}")
				server.ssend(client, Packet({"ok": True}), _enc and not srv_disable_encryption)

			elif packet.get("get_address"):
				test_nn = packet.get("get_address")
				if test_nn in nn_conn:
					server.ssend(client, Packet({"address": nn_ls[test_nn]}), _enc and not srv_disable_encryption)
				else:
					server.ssend(client, Packet({"address": False}), _enc and not srv_disable_encryption)

			elif packet.get("disconnect"):
				server.stop_handler(th_id)

			else:
				getter = packet.get("to", None)
				if getter == None:
					continue

				if getter == "server":
					content = packet.get("content", None)
					logging.info(f"[{nn}] {content}")
					continue

				elif getter == nn:
					continue

				conn = nn_conn.get(getter, None)
				has_enc = True if server._encryptes.get(conn, None) else False
				if conn != None:
					server.ssend(conn, packet, has_enc and not srv_disable_encryption)
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
		try:
			name = next(k for k, v in nn_ls.items() if v == addr_str)
		except StopIteration:
			name = None
		display_name = name if name else "UNKNOWN"
		logging.info(f"{display_name} has been disconnected")

		if name:
			nn_ls.pop(nn, None)
			nn_conn.pop(name, None)
			th_ids.pop(name, None)
		# client.close()
		try:
			run_async_ctx(loop, client.close())
		except TimeoutError:
			logging.warning(f"TimeoutError while closing connection for {display_name}")
		server.stop_handler(th_id)


cmdm = None
current_getter = "server"


def client_handle_4hndl(client: Client):
	...


def cmd_handle_4hndl(client: Client):
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


def handle_client_4clnt(client: Client):
	asyncio.gather(client_handle_4hndl(client), cmd_handle_4hndl(client))


def main(args):
	global srv_disable_encryption

	use_cnf = not args.no_use_config
	mode = 0 if args.server else 1
	ui_mode = 1 if args.webui else 0
	config = Config("settings.conf") if use_cnf else None
	srv_disable_encryption = args.disable_encryption

	if srv_disable_encryption:
		logging.warning("Server encryption is disabled. This is not recommended for security reasons.")

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

	
	def start_udp_hole_punching(addr) -> bool:
		import socket
		srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		srv.bind((addr, 9000))
		srv.listen(16)

		while True:
			conn, addr = srv.accept()
			threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

	def start_webui_thread():
		import uvicorn
		import api.webui as webui
		def _run(): uvicorn.run(webui.app, host="127.0.0.1", port=8000+random.randint(0, 999), access_log=False)
		threading.Thread(target=_run, daemon=True).start()


	logging.info(f"Mode: {mode}; Use config: {use_cnf}; UI mode: {ui_mode}")

	if mode == 0 and ui_mode == 0:
		async def start_server():
			global handle_client_4srv
			server = await Server.create(args.port, MAX_SIZE_SYNC_PACKET)

			if args.udp_hole_punching:
				threading.Thread(target=start_udp_hole_punching, args=[args.host], daemon=True).start()

			server.setClientHandler(handle_client_4srv)
			await server.start()

		aloop = get_async_ctx(__name__)
		run_async_ctx(aloop, start_server(), timeout=None)

	if mode == 1 and ui_mode == 0:
		import getpass
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
		password = getpass.getpass("Enter password: ")
		if use_cnf:
			config.save()

		client = Client(addr, port, nickname, password, MAX_SIZE_SYNC_PACKET)
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
	try:
		import argparse
		parser = argparse.ArgumentParser()
		parser.add_argument("--no-use-config", "-nuc", action="store_true", help="Don't use config file")
		parser.add_argument("--server", "-s", action="store_true", help="Start in server mode")
		parser.add_argument("--webui", "-w", action="store_true", help="Start with web UI")
		parser.add_argument("--udp-hole-punching", "-u", action="store_true", help="Enable Server UDP hole punching (experimental)")
		parser.add_argument("--disable-encryption", "-de", action="store_true", help="Disable encryption (not recommended, Server-side argument)")
		parser.add_argument("--host", "-H", type=str, default="127.0.0.1", help="Address for run server")
		parser.add_argument("--port", "-p", type=int, default=1414, help="Port for run server")
		args = parser.parse_args()
		main(args)
	except KeyboardInterrupt:
		pass