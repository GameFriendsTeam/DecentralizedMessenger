import json

class Packet:
	def __init__(self, data: dict):
		self.data = data

	def get(self, key, default = None):
		return self.data.get(key, default)

	def getAll(self) -> dict:
		return self.data

	def set(self, key, value) -> None:
		self.data[key] = value

	def getStr(self) -> str:
		return json.dumps(self.data)

	def __str__(self) -> str:
		return self.getStr()

	def __bytes__(self) -> bytes:
		return self.getStr().encode("utf-8")

	def __len__(self) -> int:
		return len(self.getStr())

	def __getitem__(self, name):
		return self.data.get(name, None)

	@staticmethod
	def fromRaw(rawPacket):

		t = type(rawPacket)
		if rawPacket == None:
			print(rawPacket)

		try:
			if t is bytes:
				return Packet(json.loads(rawPacket.decode("utf-8")))
			elif t is str:
				return Packet(json.loads(rawPacket))
			elif t is dict:
				return Packet(rawPacket)
		except json.JSONDecodeError:
			return Packet({})

	@staticmethod
	def staticPacket(data, max_len) -> str:
		packet0 = Packet(data)
		pl0 = len(packet0)

		if pl0 > max_len:
			raise Exception("Length limit!")

		remnant = max_len - pl0
		packet_noise = "b"*remnant

		return str(packet0)+packet_noise
