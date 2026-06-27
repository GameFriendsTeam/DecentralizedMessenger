import socket
import threading, uuid


class UDPServer:
	started: bool = False
	socket: socket.socket
	targetPort: int
	_clients: dict = {}
	
	def __init__(self, port, mssp):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.targetPort = port
		self.size_sync_p = mssp

	def send(self, targetAddr: str, targetPort: int, rawPacket: bytes):
		self.socket.sendto(rawPacket, (targetAddr, targetPort))

	def read(self, buffer: int = None) -> tuple[bytes, tuple[str, int]]:
		if buffer is None:
			buffer = self.size_sync_p or 4096
		return self.socket.recvfrom(buffer)

	def setClientHandler(self, handler):
		self._handler = handler

	def start(self):
		# Bind and start a background handler thread; handler is responsible for calling read()
		self.socket.bind(("0.0.0.0", self.targetPort))
		self.started = True
		if hasattr(self, '_handler') and self._handler:
			threading.Thread(target=self._handler, args=(self,), daemon=True).start()

	def stop(self):
		self.started = False
		try:
			self.socket.close()
		except Exception:
			pass

	def isStarted(self):
		return self.started