from api.Packet import Packet
from api.utils.Encryption import Encryption
from api.utils.Other import bytes_to_base64, base64_to_bytes
import json

class EncryptedPacket(Packet):
	def __init__(self, data: dict, encrypt: Encryption):
		self.data = data
		self.encrypt = encrypt

	def get(self, key, default = None):
		return self.data.get(key, default)

	def getAll(self) -> dict:
		return self.data

	def set(self, key, value) -> None:
		self.data[key] = value
		self._cached_str = None

	def getStr(self) -> str:
		if not hasattr(self, "_cached_str") or self._cached_str is None:
			normal = json.dumps(self.data)
			nonce, ciphertext = self.encrypt.encrypt_message(normal.encode("utf-8"))

			self._cached_str = json.dumps([bytes_to_base64(nonce), bytes_to_base64(ciphertext)])
		return self._cached_str

	def __str__(self) -> str:
		return self.getStr()

	def __bytes__(self) -> bytes:
		return self.getStr().encode("utf-8")

	def __len__(self) -> int:
		return len(self.getStr())

	def __getitem__(self, name):
		return self.data.get(name, None)

	@staticmethod
	def fromRaw(encrypted, encrypt: Encryption):
		if isinstance(encrypted, bytes):
			encrypted = encrypted.decode("utf-8")
		nonce_raw, ciphertext_raw = json.loads(encrypted)
		nonce = base64_to_bytes(nonce_raw)
		ciphertext = base64_to_bytes(ciphertext_raw)
		normal = encrypt.decrypt_message(nonce, ciphertext)
		return EncryptedPacket(json.loads(normal), encrypt)

	@staticmethod
	def staticPacket(data, max_len: int, encrypt: Encryption) -> str:
		packet0 = EncryptedPacket(data, encrypt)
		pl0 = len(packet0)

		enc_alert = "encrypted"
		enc_len = len(enc_alert)

		if pl0+enc_len > max_len:
			raise Exception("Length limit!")

		remnant = max_len - pl0 - enc_len
		packet_noise = f":{enc_alert}"+"b"*(remnant-1)

		return str(packet0)+packet_noise

	@staticmethod
	def extractPayload(raw: str) -> str:
		"""Отрезает паддинг ':encryptedbbb...' и возвращает чистый JSON-массив [nonce, ciphertext]."""
		packetEnd = raw.rfind(']')
		return raw[:packetEnd + 1]
