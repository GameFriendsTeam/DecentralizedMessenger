import socket
import threading
import json


class Server:
	started: bool = False
	socket: socket.socket
	targetPort: int

	def __init__(self, port):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.targetPort = port

	def send(self, socket_obj, rawData):
		socket_obj.send(rawData.encode("utf-8"))

	def read(self, socket_obj):
		return socket_obj.recv(1024).decode("utf-8")
	def setClientHandler(self, handler):
		self._handler = handler

	def start(self):
		self.socket.bind(("localhost", self.targetPort))
		self.started = True
		self.socket.listen()

		while self.started:
			cl_sock, addr = self.socket.accept()
			if cl_sock and addr:
				threading.Thread(target=self._handler, args=[self, cl_sock, addr]).start()

	def stop(self):
		self.started = False
		try:
			self.socket.close()
		except Exception:
			pass

	def isStarted(self):
		return self.isStarted


def clnt_hand_4srv(srv, clnt, clnt_addr):
	...


def main():
	...

if __name__ == '__main__':
	main()