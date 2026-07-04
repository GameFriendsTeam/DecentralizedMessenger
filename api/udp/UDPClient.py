import socket


class UDPClient:
	started: bool = False
	socket: socket.socket
	targetAddr: str
	targetPort: int
	username: str

	def __init__(self, 
		addr: str, port: int,
		username: str,
		mssp: int
	):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.started = False
		self.targetAddr = addr
		self.targetPort = port
		self.size_sync_p = mssp
		self.username = username


	def send(self, *args):
		# support send(rawPacket) or send(targetAddr, targetPort, rawPacket)
		if len(args) == 1:
			rawPacket = args[0]
			self.socket.sendto(rawPacket, (self.targetAddr, self.targetPort))
		elif len(args) == 3:
			targetAddr, targetPort, pkt = args
			self.socket.sendto(pkt, (targetAddr, targetPort))
		else:
			raise TypeError("send expects (rawPacket) or (targetAddr, targetPort, rawPacket)")

	def read(self, buffer: int = 1024) -> bytes:
		# return next packet coming from configured target
		while True:
			rawPacket, addr = self.socket.recvfrom(buffer)
			if addr[0] == self.targetAddr and addr[1] == self.targetPort:
				return rawPacket


	def setThread(self, th):
		self._th = th


	def start(self):
		self.socket.connect((self.targetAddr, self.targetPort))
		self.started = True

		th = self._th
		th(self)
		self.stop()

	def stop(self):
		if self.socket != None: self.socket.close()
		self.started = False

	def isStarted(self): return self.started