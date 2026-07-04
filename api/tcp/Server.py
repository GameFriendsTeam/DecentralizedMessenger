import socket
from typing import Optional
import threading, uuid
from api.Packet import Packet
from api.EncryptedPacket import EncryptedPacket
from api.tcp.Client import Client
from api.utils.Other import load_public_key, recv_exact, base64_to_bytes, bytes_to_base64
from api.utils.Encryption import Encryption


class Server:
	started: bool = False
	socket: socket.socket
	targetPort: int
	_clients: dict = {}
	_ths: dict = {}
	
	def __init__(self, port, mssp):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.serverClient = False
		self.targetPort = port
		self.size_sync_p = mssp
		self._shared_uuid = str(uuid.uuid4())
		self._clients = {}
		self._handlers = {}
		self._ths = {}
		self._encryptes = {}


	def init_encrypt(self, obj):
		if obj in self._encryptes:
			return self._encryptes[obj]
		enc = Encryption()
		pr_k, pub_k = enc.generate_keypair()
		key_bytes = enc.serialize_public_key()
		pkt = Packet({"key": bytes_to_base64(key_bytes)})
		self.send(obj, pkt)
		newPkt, _ = self.read(obj)
		obj_key = base64_to_bytes(newPkt.get("key"))
		enc.derive_shared_key(load_public_key(obj_key))
		self._encryptes[obj] = enc
		return enc


	def send(self, socket_obj, packet: Packet, encrypt: bool = False):
		packet_len = len(packet)
		if encrypt:
			self.send_ecryptedpkt(socket_obj, packet.getAll())
			return

		lenPacket = Packet.staticPacket({"len": packet_len}, self.size_sync_p)
		socket_obj.send(lenPacket.encode("utf-8"))
		socket_obj.send(bytes(packet))

	def send_ecryptedpkt(self, socket_obj, data: dict):
		enc = self.init_encrypt(socket_obj)
		packet = EncryptedPacket(data, enc)
		packet_len = len(packet)

		lenPacket = EncryptedPacket.staticPacket({"len": packet_len}, self.size_sync_p, enc)
		socket_obj.send(lenPacket.encode("utf-8"))
		socket_obj.send(bytes(packet))


	def read(self, socket_obj) -> tuple[Packet, bool]:
		"""
		Read packet from socket_obj
		Returns:
			Tuple[Packet, bool]
			  - Packet - read packet
			  - bool - is encrypted
		"""
		rawLen = recv_exact(socket_obj, self.size_sync_p).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None, False
		packetEnd = rawLen.rfind('}')
		if packetEnd < 0:
			return self.read_ecryptedpkt(socket_obj, rawLen), True

		lenPacket = Packet.fromRaw(rawLen[:packetEnd + 1])["len"]
		rawPacket = recv_exact(socket_obj, lenPacket)
		if not rawPacket or lenPacket < 1:
			return None, False

		return Packet.fromRaw(rawPacket), False

	def read_ecryptedpkt(self, socket_obj, rawLen: Optional[str] = None) -> EncryptedPacket:
		enc = self.init_encrypt(socket_obj)
		if not rawLen:
			rawLen = recv_exact(socket_obj, self.size_sync_p).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None

		if rawLen.find(":encrypted") < 0:
			return None

		payload = EncryptedPacket.extractPayload(rawLen)
		lenPacket = EncryptedPacket.fromRaw(payload, enc)["len"]
		rawPacket = recv_exact(socket_obj, lenPacket)
		if not rawPacket or lenPacket < 1:
			return None

		return EncryptedPacket.fromRaw(rawPacket, enc)


	def setClientHandler(self, handler):
		self._handler = handler

	def start(self):
		print("Bind addr to server")
		self.socket.bind(("localhost", self.targetPort))
		self.started = True
		print(f"Server has listening on {self.targetPort}")
		self.socket.listen()

		while self.started:
			cl_sock, addr = self.socket.accept()
			th_id = len(self._handlers)
			self._handlers[th_id] = threading.Thread(target=self._handler, args=[self, cl_sock, addr, th_id], daemon=True)
			self._handlers[th_id].start()

	def stop_handler(self, th_id):
		if not th_id in self._handlers:
			return
		thread = self._handlers[th_id]
		# Поток не может ждать (join) сам себя — это вызывает RuntimeError.
		# Если stop_handler вызван из самого потока-обработчика (например, в ответ
		# на packet.get("disconnect") или в блоке finally при выходе), просто
		# убираем запись из реестра без join: поток и так сейчас завершается.
		if thread is not threading.current_thread():
			thread.join()
		self._handlers.pop(th_id, None)

	def stop(self):
		self.started = False
		try:
			self.socket.close()
		except Exception:
			pass

	def isStarted(self):
		return self.started


	def addInternalClient(self, client: Client) -> int:
		identificator = len(self._clients)

		def _handle(client):
			while client.isStarted():
				try:
					s_in, _enc = client.read()
					if s_in is not None and s_in.get('to', 'server') == client.getUsername():
						print(f"{s_in.get('from', 'unknown')}: {s_in.get('content', '[NULL]')}\n")
					else:
						try:
							client.transmit(s_in, _enc)
						except Exception as ex:
							print(ex)
				except Exception as ex:
					print(ex)
		client.setUsername(f"server-{self._shared_uuid}")
		client.setThread(_handle)

		self._clients[identificator] = client

		th = threading.Thread(target=client.start, daemon=True)
		th.start()
		self._ths[identificator] = th

		return identificator

	def removeInternalClient(self, identificator: int):
		self._clients.pop(identificator, None)

	def getInternalClient(self, identificator: int = None) -> Client:
		if identificator is None:
			# return first internal client if any
			return next(iter(self._clients.values()), None)
		return self._clients.get(identificator, None)
	
	def getAllInternalClients(self) -> dict:
		return self._clients


	def send_key(self, to: str) -> Packet:
		raise NotImplementedError("Server-side key exchange is not implemented in this helper")

	def read_key(self, sender: str):
		raise NotImplementedError("Server-side key exchange is not implemented in this helper")