from api.utils.Encryption import Encription
import json

class EncryptedPacket:
	def __init__(self, data: dict, encrypt: Encription):
		self.data = data
		self.encrypt = encrypt

	def get(self, key, default = None):
		return self.data.get(key, default)

	def getAll(self) -> dict:
		return self.data

	def set(self, key, value) -> None:
		self.data[key] = value

	def getStr(self) -> str:
		normal = json.dumps(self.data)
		nonce, chipertext = self.encrypt.encrypt_message(normal)
		encrypted = f"{list(nonce)}:{list(chipertext)}"
		return encrypted

	def __str__(self) -> str:
		return self.getStr()

	def __bytes__(self) -> bytes:
		return self.getStr().encode("utf-8")

	def __len__(self) -> int:
		return len(self.getStr())

	def __getitem__(self, name):
		return self.data.get(name, None)

	@staticmethod
	def fromRaw(encrypted: str, encrypt: Encription):
		nonce, chipertext = encrypted.split()
		normal = encrypt.decrypt_message(bytes(nonce), bytes(chipertext))
		return EncryptedPacket(json.loads(normal), encrypt)

	@staticmethod
	def staticPacket(data, max_len: int, encrypt: Encription) -> str:
		packet0 = EncryptedPacket(data, encrypt)
		pl0 = len(packet0)

		enc_alert = "encrypted"
		enc_len = len(enc_alert)

		if pl0+enc_len > max_len:
			raise Exception("Length limit!")

		remnant = max_len - pl0 - enc_len
		packet_noise = f":{enc_alert}"+"b"*(remnant-1)

		return str(packet0)+packet_noise
