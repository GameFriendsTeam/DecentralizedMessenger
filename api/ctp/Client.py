import asyncio
import logging
import time
import threading
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import x25519
from api.commands.CommandSender import CommandSender
from api.protocol.stream import Stream
from api.utils.Encryption import Encryption, SecureEncryption
from api.protocol.endpoint import Endpoint
from api.Packet import Packet
from api.EncryptedPacket import EncryptedPacket
from api.utils.Other import load_public_key, base64_to_bytes, bytes_to_base64
from api.utils.Other import get_async_ctx, run_async_ctx
import multiprocessing as mp


class Client(CommandSender):
	_stream: Stream
	_loop: asyncio.AbstractEventLoop
	started: bool = False
	targetAddr: str
	targetPort: int
	username: str

	def __init__(self, addr: str, port: int, username: str, password: str, mssp: int):
		self._loop = get_async_ctx(self.__class__.__name__)
		_ep = run_async_ctx(self._loop, Endpoint.create(host=("127.0.0.1" if addr == "127.0.0.1" else "0.0.0.0"), port=0))
		conn = _ep.connect((addr, port))

		self._stream = conn.open_stream(0, True, True)
		try:
			run_async_ctx(self._loop, self._stream.sync(), timeout=5.0)
		except TimeoutError:
			raise Exception(f"Timeout while waiting for sending sync packet to {addr}:{port}")

		self.started = False
		self.packets = {}
		self.targetAddr = addr
		self.targetPort = port
		self.size_sync_p = mssp
		self.username = username
		self.password = password
		self.encripts = {} # Of SecureEncryption
		self.srv_enc = Encryption()
		

	def getUsername(self): return self.username
	def sendUsername(self):
		if not self.started or self.username == "": return
		packet = Packet({"name": self.username, "password": self.password})
		self.send(packet, True)


	def setUsername(self, username):
		if username == "": return
		self.username = username
		self.sendUsername()


	def send(self, packet: Packet, encrypt: bool = False):
		if encrypt and self.connectionIsSecure():
			self.send_ecryptedpkt(packet.getAll())
			return
		packet_len = len(packet)

		lenPacket = Packet.staticPacket({"len": packet_len}, self.size_sync_p)
		run_async_ctx(self._loop, self._stream.send(str(lenPacket).encode("utf-8")))
		run_async_ctx(self._loop, self._stream.send(bytes(packet)))

	def send_ecryptedpkt(self, data: dict):
		enc = self.srv_enc
		packet = EncryptedPacket(data, enc)
		packet_len = len(packet)

		lenPacket = EncryptedPacket.staticPacket({"len": packet_len}, self.size_sync_p, enc)
		run_async_ctx(self._loop, self._stream.send(lenPacket.encode("utf-8")))
		run_async_ctx(self._loop, self._stream.send(bytes(packet)))


	def read(self, timeout: int = 6) -> tuple[Packet, bool]:
		"""
		Read packet
		Returns:
			Tuple[Packet, bool]
			  - Packet - read packet
			  - bool - is encrypted
		"""
		rawLen = run_async_ctx(self._loop, self._stream.recv(), timeout).decode("utf-8")
		if rawLen == None or rawLen == "": return None, False
		packetEnd = rawLen.rfind('}')
		if packetEnd < 0 and self.connectionIsSecure():
			return self.read_ecryptedpkt(rawLen), True
		rawLen = rawLen[:packetEnd + 1]

		lenPacket = Packet.fromRaw(rawLen).get("len", 128)
		rawPacket = run_async_ctx(self._loop, self._stream.recv(), timeout)
		if not rawPacket or lenPacket < 1: return None, False

		return Packet.fromRaw(rawPacket), False

	def read_ecryptedpkt(self, rawLen: Optional[str] = None, timeout: int = 6) -> EncryptedPacket:
		if not self.connectionIsSecure():
			return None
		enc = self.srv_enc
		if not rawLen:
			rawLen = run_async_ctx(self._loop, self._stream.recv(), timeout).decode("utf-8")
		if rawLen is None or rawLen == "":
			return None

		if rawLen.find(":encrypted") < 0:
			return None

		payload = EncryptedPacket.extractPayload(rawLen)
		lenPacket = EncryptedPacket.fromRaw(payload, enc)["len"]
		rawPacket = run_async_ctx(self._loop, self._stream.recv(), timeout)
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
		#self.socket.connect((self.targetAddr, self.targetPort))
		self.started = True

		self._packet_th = threading.Thread(target=self.packet_handler, daemon=True)
		self._packet_th.start()

		try:
			data = self.wait_packet("key_exchange", timeout=15)
			srv_key = None

			if not data:
				logging.error("No key exchange packet received. Secure connection will not be used.")
				self.srv_enc = None
			else:
				srv_key, _ = data

			if srv_key is None or srv_key.get("no_encryption"):
				raise Exception("Server has encryption disabled")
	
			self.srv_enc.generate_keypair()
			key_bytes = self.srv_enc.serialize_public_key()
			pkt = Packet({"type": "key_exchange", "key": bytes_to_base64(key_bytes)})

			self.send(pkt)
			self.srv_enc.derive_shared_key(load_public_key(base64_to_bytes(srv_key.get("key"))))
		except Exception as exc:
			logging.error(f"Error while establishing secure connection: {exc}. Secure connection will not be used.")
			self.srv_enc = None

		self.sendUsername()
		data = self.wait_packet("ready", timeout=15)
		if not data:
			logging.error("No ready packet received. Connection may not be fully established.")
			self.started = False
			return
		_, _enc = data
		self.send(Packet({"type": "ready", "ready": True}), _enc)
		logging.info("Ready!")

		th = self._th
		th(self)
		self.stop()


	def stop(self):
		self.started = False
		try:
			self.send(Packet({"type": "connection_info", "disconnect": True}), True)
			self._packet_th.join()
		except ConnectionError:
			...
		except BrokenPipeError:
			...
		except Exception as exc:
			logging.info(f"Exception: {exc}")
		finally:
			#self.socket.close()
			self._loop.stop()

	def isStarted(self): return self.started


	def transmit(self, packet: Packet, encrypt: bool = False):
		if not self.started: raise Exception("Client socket is closed")
		packet.set("transmit", True)
		self.send(packet, encrypt)


	def _cc(self, timeout: int):
		"""Check connection by sending ping and waiting up to timeout seconds."""
		ts = time.time()
		self.send(Packet({"type": "cc", "ping": timeout, "timestamp": ts}), True)

		server_status = self.wait_packet("cc", timeout)[0].get("ok", False)
		end_ts = time.time()
		status = server_status and (end_ts-ts<=timeout*1000)
		return (status, (end_ts-ts))

	def checkConnection(self, timeout: int) -> bool:
		try:
			status, time = self._cc(timeout)
		except TimeoutError:
			return False, 0

		return status, time


	def connectionIsSecure(self) -> bool:
		return self.srv_enc != None


	def _init_encript(self, to: str):
		encript = self.encripts.get(to, None)
		if encript:
			return encript

		encript = SecureEncryption(self.getUsername())
		encript.generate_signing_keypair()
		encript.generate_keypair()

		self.encripts[to] = encript
		return encript

	def get_encript(self, to: str) -> Optional[SecureEncryption]:
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

		self.send(Packet(packet_data), True)

	def read_key(self, sender: str, timeout: int = 6):
		encript = self._init_encript(sender)

		packet_with_key = None

		while not packet_with_key:
			packet, _ = self.wait_packet("key_exchange", timeout)
			logging.info(packet)
			if packet.get("signature"):
				packet_with_key = packet

		if not packet_with_key:
			logging.info("Packet with key not given")
			return
		peer_x25519_pub = base64_to_bytes(packet_with_key["x25519_pub"])
		peer_ed25519_pub = base64_to_bytes(packet_with_key["ed25519_pub"])
		peer_sig = base64_to_bytes(packet_with_key["signature"])

		if not encript.verify_signature(
			peer_x25519_pub + self.getUsername().encode("utf-8"),
			peer_sig,
			peer_ed25519_pub
		):
			logging.info("Invalid signature!")
			return

		encript.verify_peer_manually(
			sender,
			peer_ed25519_pub,
			peer_x25519_pub
		)

		peer_key = x25519.X25519PublicKey.from_public_bytes(peer_x25519_pub)
		encript.derive_shared_key(peer_key)


	def packet_handler(self):
		while self.started:
			try:
				data = self.read(None)
				if not data:
					continue
				packet, _enc = data
				logging.debug(f"Packet received: {packet}, encrypted: {_enc}")
				pkt_type = packet.get("type", "unknown")
				if pkt_type:
					self.packets[pkt_type] = packet, _enc
			except RuntimeError as exc:
				logging.error(f"Runtime error while reading packet: {exc}")
			except Exception as exc:
				logging.error(f"Error while reading packet: {exc}")


	def get_packet(self, type_p: str):
		return self.packets.get(type_p, None)


	def wait_packet(self, type_p: str, timeout: float = 5.0):
		start_time = time.time()
		while time.time() - start_time < timeout:
			pkt = self.get_packet(type_p)
			if pkt:
				return pkt
		return None