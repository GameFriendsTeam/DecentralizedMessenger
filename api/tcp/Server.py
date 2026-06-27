import socket
import threading, uuid
from api.Packet import Packet
from api.EncryptedPacket import EncryptedPacket
from api.tcp.Client import Client
from api.utils.Other import load_public_key
from api.utils.Encryption import Encription
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet


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
		enc = Encription()
		pr_k, pub_k = enc.generate_keypair()
		key_bytes = enc.serialize_public_key()
		pkt = Packet({"key": list(key_bytes)})
		self.send(obj, pkt)
		newPkt = self.read(obj)
		obj_key = bytes(newPkt.get("key"))
		enc.derive_shared_key(load_public_key(obj_key))
		self._encryptes[obj] = enc
		return enc


	def send(self, socket_obj, packet: Packet):
		packet_len = len(packet)

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


	def read(self, socket_obj) -> Packet:
		rawLen = socket_obj.recv(self.size_sync_p).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None
		packetEnd = rawLen.rfind('}')

		lenPacket = Packet.fromRaw(rawLen[:packetEnd + 1])["len"]
		rawPacket = socket_obj.recv(lenPacket)
		if rawPacket is None or lenPacket < 1:
			return None

		return Packet.fromRaw(rawPacket)

	def read_ecryptedpkt(self, socket_obj) -> EncryptedPacket:
		enc = self.init_encrypt(socket_obj)
		rawLen = socket_obj.recv(self.size_sync_p).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None
		packetEnd = rawLen.rfind('}')

		if rawLen.find(":encrypted") < 0:
			return None

		lenPacket = Packet.fromRaw(rawLen[:packetEnd + 1])["len"]
		rawPacket = socket_obj.recv(lenPacket)
		if rawPacket is None or lenPacket < 1:
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
		self._handlers[th_id].join()
		self._handlers.pop(th_id)

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
					s_in = client.read()
					if s_in is not None and s_in.get('to', 'server') == client.getUsername():
						print(f"{s_in.get('from', 'unknown')}: {s_in.get('content', '[NULL]')}\n")
					else:
						try:
							client.transmit(s_in)
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
