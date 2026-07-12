import asyncio
import logging
import socket
from typing import Optional
import threading, uuid
from api.Packet import Packet
from api.EncryptedPacket import EncryptedPacket
from api.hp.Server import handle_client
from api.protocol import Stream, Endpoint
from api.ctp.Client import Client
from api.utils.Other import load_public_key, base64_to_bytes, bytes_to_base64, run_async_ctx
from api.utils.Encryption import Encryption


class Server:


	def __init__(self):
		self.started: bool = False
		self._ep: Endpoint
		self.targetPort: int
		self._clients: dict = {}
		self._ths: dict = {}
		self._encryptes: dict = {}
		self._handlers: dict = {}
		self.loop: asyncio.AbstractEventLoop
		self.size_sync_p: int


	@classmethod
	async def create(cls, port: int, mssp: int, run_hp: bool = False) -> "Server":
		self = cls()
		self._ep = await Endpoint.create(host="0.0.0.0", port=port)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.serverClient = False
		self.targetPort = port
		self._shared_uuid = str(uuid.uuid4())
		self.loop = asyncio.get_running_loop()
		self.size_sync_p = mssp
		return self


	async def init_encrypt(self, obj):
		if obj in self._encryptes:
			return self._encryptes[obj]
		enc = Encryption()
		pr_k, pub_k = enc.generate_keypair()
		key_bytes = enc.serialize_public_key()
		pkt = Packet({"type": "key_exchange", "key": bytes_to_base64(key_bytes)})
		await self.send(obj, pkt)
		newPkt, _ = await self.read(obj)
		obj_key = base64_to_bytes(newPkt.get("key"))
		enc.derive_shared_key(load_public_key(obj_key))
		self._encryptes[obj] = enc
		return enc
	
	def sinit_encrypt(self, obj):
		run_async_ctx(self.loop, self.init_encrypt(obj), timeout=5.0)


	async def send(self, socket_obj: Stream, packet: Packet, encrypt: bool = False):
		packet_len = len(packet)
		if encrypt:
			await self.send_ecryptedpkt(socket_obj, packet.getAll())
			return

		lenPacket = Packet.staticPacket({"len": packet_len}, self.size_sync_p)
		await socket_obj.send(lenPacket.encode("utf-8"))
		await socket_obj.send(bytes(packet))

	def ssend(self, socket_obj: Stream, packet: Packet, encrypt: bool = False):
		run_async_ctx(self.loop, self.send(socket_obj, packet, encrypt), timeout=5.0)


	async def send_ecryptedpkt(self, socket_obj: Stream, data: dict):
		enc = await self.init_encrypt(socket_obj)
		packet = EncryptedPacket(data, enc)
		packet_len = len(packet)

		lenPacket = EncryptedPacket.staticPacket({"len": packet_len}, self.size_sync_p, enc)
		await socket_obj.send(lenPacket.encode("utf-8"))
		await socket_obj.send(bytes(packet))
	
	def ssend_ecryptedpkt(self, socket_obj: Stream, data: dict):
		run_async_ctx(self.loop, self.send_ecryptedpkt(socket_obj, data), timeout=5.0)


	async def read(self, socket_obj: Stream) -> tuple[Packet, bool]:
		"""
		Read packet from socket_obj
		Returns:
			Tuple[Packet, bool]
			  - Packet - read packet
			  - bool - is encrypted
		"""
		rawLen = await socket_obj.recv()
		rawLen = rawLen.decode("utf-8")
		if rawLen is None or rawLen == "":
			return None, False
		packetEnd = rawLen.rfind('}')
		if packetEnd < 0:
			return await self.read_ecryptedpkt(socket_obj, rawLen), True

		lenPacket = Packet.fromRaw(rawLen[:packetEnd + 1])["len"]
		rawPacket = await socket_obj.recv()
		if not rawPacket or lenPacket < 1:
			return None, False

		return Packet.fromRaw(rawPacket), False
	
	def sread(self, socket_obj: Stream, t: int = None) -> tuple[Packet, bool]:
		return run_async_ctx(self.loop, self.read(socket_obj), timeout=t)


	async def read_ecryptedpkt(self, socket_obj: Stream, rawLen: Optional[str] = None) -> EncryptedPacket:
		enc = await self.init_encrypt(socket_obj)
		if not rawLen:
			rawLen = await socket_obj.recv()
			rawLen = rawLen.decode("utf-8")
		if rawLen is None or rawLen == "":
			return None

		if rawLen.find(":encrypted") < 0:
			return None

		payload = EncryptedPacket.extractPayload(rawLen)
		lenPacket = EncryptedPacket.fromRaw(payload, enc)["len"]
		rawPacket = await socket_obj.recv()
		if not rawPacket or lenPacket < 1:
			return None

		return EncryptedPacket.fromRaw(rawPacket, enc)
	
	def sread_ecryptedpkt(self, socket_obj: Stream, rawLen: Optional[str] = None, t: int = None) -> EncryptedPacket:
		return run_async_ctx(self.loop, self.read_ecryptedpkt(socket_obj, rawLen), timeout=t)


	def setClientHandler(self, handler):
		self._handler = handler

	async def start(self):
		logging.info("Bind addr to server")
		self.socket.bind(("localhost", self.targetPort))
		self.started = True
		logging.info(f"Server has listening on {self.targetPort}")
		#self.socket.listen()
		self._hp_thread = threading.Thread(target=self.hp_srv, daemon=True)
		self._hp_thread.start()

		while self.started:
			try:
				conn = await self._ep.accept()
				logging.info(f"New connection from {conn.remote_addr}")
				stream = await conn.get_stream(0)
				await stream.sync()
				addr = conn.remote_addr
				th_id = len(self._handlers)
				self._handlers[th_id] = threading.Thread(target=self._handler, args=[self, stream, addr, th_id], daemon=True)
				self._handlers[th_id].start()
			except TimeoutError:
				...
			except Exception as ex:
				logging.info(f"Error accepting connection: {ex}")


	def stop_handler(self, th_id):
		if not th_id in self._handlers:
			return
		thread = self._handlers[th_id]
		if thread is not threading.current_thread():
			thread.join()
		self._handlers.pop(th_id, None)

	def stop(self):
		self.started = False
		try:
			self.socket.close()
		except Exception:
			pass

		if hasattr(self, '_hp_thread'):
			self._hp_thread.join()


	def isStarted(self):
		return self.started


	def addInternalClient(self, client: Client) -> int:
		identifier = len(self._clients)

		def _handle(client):
			while client.isStarted():
				try:
					s_in, _enc = client.wait_packet("message", timeout=5.0)
					if s_in is not None and s_in.get('to', 'server') == client.getUsername():
						logging.info(f"{s_in.get('from', 'unknown')}: {s_in.get('content', '[NULL]')}\n")
					else:
						try:
							client.transmit(s_in, _enc)
						except Exception as ex:
							logging.info(ex)
				except Exception as ex:
					logging.info(ex)
		client.setUsername(f"server-{self._shared_uuid}")
		client.setThread(_handle)

		self._clients[identifier] = client

		th = threading.Thread(target=client.start, daemon=True)
		th.start()
		self._ths[identifier] = th

		return identifier

	def removeInternalClient(self, identifier: int):
		self._clients.pop(identifier, None)

	def getInternalClient(self, identifier: int = None) -> Client:
		if identifier is None:
			# return first internal client if any
			return next(iter(self._clients.values()), None)
		return self._clients.get(identifier, None)

	def getAllInternalClients(self) -> dict:
		return self._clients


	def send_key(self, to: str) -> Packet:
		raise NotImplementedError("Server-side key exchange is not implemented in this helper")

	def read_key(self, sender: str):
		raise NotImplementedError("Server-side key exchange is not implemented in this helper")
	

	def hp_srv(self):
		srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		srv.bind(("0.0.0.0", self.targetPort))
		srv.listen(100)

		while True:
			conn, addr = srv.accept()
			threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()