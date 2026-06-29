from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
from api.utils.Encryption import Encryption, FileEncryption, SecureEncryption
import socket, threading, time
from api.Packet import Packet
from api.EncryptedPacket import EncryptedPacket
from api.utils.Other import load_public_key, recv_exact, base64_to_bytes, bytes_to_base64


class Client:
	serverClient: bool
	started: bool = False
	socket: socket.socket
	targetAddr: str
	targetPort: int
	username: str

	def __init__(self, addr: str, port: int, username: str, mssp: int):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.serverClient = False
		self.started = False
		self.targetAddr = addr
		self.targetPort = port
		self.size_sync_p = mssp
		self.username = username
		self.encripts = {} # Of SecureEncryption
		self.srv_enc = Encryption()
		

	def getUsername(self): return self.username
	def sendUsername(self):
		if not self.started or self.username == "": return
		packet = Packet({"name":self.username})
		self.send(packet)


	def setUsername(self, username):
		if username == "": return
		self.username = username
		self.sendUsername()


	def send(self, packet: Packet):
		packet_len = len(packet)

		lenPacket = Packet.staticPacket({"len": packet_len}, self.size_sync_p)
		self.socket.send(str(lenPacket).encode("utf-8"))
		self.socket.send(bytes(packet))

	def send_ecryptedpkt(self, socket_obj, data: dict):
		enc = self.srv_enc
		packet = EncryptedPacket(data, enc)
		packet_len = len(packet)

		lenPacket = EncryptedPacket.staticPacket({"len": packet_len}, self.size_sync_p, enc)
		socket_obj.send(lenPacket.encode("utf-8"))
		socket_obj.send(bytes(packet))


	def read(self) -> Packet:
		rawLen = recv_exact(self.socket, self.size_sync_p).decode("utf-8")
		if rawLen == None or rawLen == "": return None
		packetEnd = rawLen.rfind('}')
		rawLen = rawLen[:packetEnd + 1]

		lenPacket = Packet.fromRaw(rawLen).get("len", 128)
		rawPacket = recv_exact(self.socket, lenPacket)
		if not rawPacket or lenPacket < 1: return None

		return Packet.fromRaw(rawPacket)

	def read_ecryptedpkt(self) -> EncryptedPacket:
		enc = self.srv_enc
		rawLen = recv_exact(self.socket, self.size_sync_p).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None

		if rawLen.find(":encrypted") < 0:
			return None

		payload = EncryptedPacket.extractPayload(rawLen)
		lenPacket = EncryptedPacket.fromRaw(payload, enc)["len"]
		rawPacket = recv_exact(self.socket, lenPacket)
		if not rawPacket or lenPacket < 1:
			return None

		return EncryptedPacket.fromRaw(rawPacket, enc)


	def decrypt(self, pkt: Packet) -> bytes:
		sender = pkt.get("from", None)
		if sender == None:
			return None

		encript = self.get_encript(sender)
		if not encript:
			return None
		if pkt.get("to", None) != self.getUsername():
			return None

		encrypted = pkt.get("encrypted")
		nonce = encrypted[0]
		ciphertext = encrypted[1]

		decrypted = encript.decrypt_message(base64_to_bytes(nonce), base64_to_bytes(ciphertext)).decode("utf-8")
		return decrypted


	def setThread(self, th):
		self._th = th


	def start(self):
		self.socket.connect((self.targetAddr, self.targetPort))

		srv_key = self.read()
		pr_k, pub_k = self.srv_enc.generate_keypair()
		key_bytes = self.srv_enc.serialize_public_key()
		pkt = Packet({"key": bytes_to_base64(key_bytes)})
		self.send(pkt)
		self.srv_enc.derive_shared_key(load_public_key(base64_to_bytes(srv_key.get("key"))))

		self.started = True
		print("Connected!")
		self.sendUsername()

		th = self._th
		th(self)
		self.stop()


	def stop(self):
		try:
			self.send(Packet({"disconnect": True}))
		except ConnectionError:
			...
		except BrokenPipeError:
			...
		except Exception as exc:
			print(f"Exception: {exc}")
		finally:
			self.socket.close()
			self.started = False

	def isStarted(self): return self.started


	def transmit(self, packet: Packet):
		if (self.socket == None and not self.started): raise Exception("Client socket is closed")
		packet.set("transmit", True)
		self.send(packet)
		
	def checkConnection(self, timeout: int) -> bool:
		"""Check connection by sending ping and waiting up to timeout seconds."""
		self.send(Packet({"ping": timeout * 1000}))

		old_to = self.socket.gettimeout()
		try:
			self.socket.settimeout(timeout)
			self.read()
			return True
		except socket.timeout:
			return False
		finally:
			try:
				self.socket.settimeout(old_to)
			except Exception:
				self.socket.settimeout(None)


	def _init_encript(self, to: str):
		encript = self.encripts.get(to, None)
		if encript:
			return encript

		encript = SecureEncryption(self.getUsername())
		encript.generate_signing_keypair()
		encript.generate_keypair()

		self.encripts[to] = encript
		return encript

	def get_encript(self, to: str) -> SecureEncryption:
		return self.encripts.get(to, None)


	def send_key(self, to: str):
		encript = self._init_encript(to)

		my_x25519_pub = encript.serialize_x25519_public()
		my_ed25519_pub = encript.serialize_ed25519_public()

		signature = encript.sign_message(
			my_x25519_pub + to.encode("utf-8")
		)

		packet_data = {
			"type": "key_exchange",
			"x25519_pub": bytes_to_base64(my_x25519_pub),
			"ed25519_pub": bytes_to_base64(my_ed25519_pub),
			"signature": bytes_to_base64(signature),
			"to": to,
			"from": self.getUsername()
		}

		self.send(Packet(packet_data))

	def read_key(self, sender: str):
		encript = self._init_encript(sender)

		packet_with_key = None

		while not packet_with_key:
			packet = self.read()
			print(packet)
			if packet.get("signature"):
				packet_with_key = packet

		if not packet_with_key:
			print("Packet with key not given")
			return None
		peer_x25519_pub = base64_to_bytes(packet_with_key["x25519_pub"])
		peer_ed25519_pub = base64_to_bytes(packet_with_key["ed25519_pub"])
		peer_sig = base64_to_bytes(packet_with_key["signature"])

		if not encript.verify_signature(
			peer_x25519_pub + self.getUsername().encode("utf-8"),
			peer_sig,
			peer_ed25519_pub
		):
			print("Invalid signature!")
			return None

		encript.verify_peer_manually(
			sender,
			peer_ed25519_pub,
			peer_x25519_pub
		)

		peer_key = x25519.X25519PublicKey.from_public_bytes(peer_x25519_pub)
		encript.derive_shared_key(peer_key)
