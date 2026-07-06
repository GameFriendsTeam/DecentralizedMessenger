import threading
import random
from typing import List

import fastapi
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.ctp.Client import Client
from api.Packet import Packet
from api.utils.Encryption import Encryption
from api.utils.Other import load_public_key


app = fastapi.FastAPI()

# serve static and templates from package
templates = Jinja2Templates(directory="api/templates")
app.mount("/static", StaticFiles(directory="api/static"), name="static")


# Simple in-memory manager for a single client instance (demo)
class ClientManager:
	def __init__(self):
		self.client: Client | None = None
		self.messages: List[dict] = []
		self.lock = threading.Lock()
		self.thread: threading.Thread | None = None
		self.encript: Encryption = Encryption()
		self.stoped: bool = False
		self.encript_enable: bool = False

	def _reader(self, client: Client):
		print("Client has been started")
		while client.isStarted():
			try:
				if self.stoped: continue

				pkt = client.read()
				if pkt is None:
					continue
				#with self.lock:
				if pkt.get("content") == "Encrypted":
					nonce = pkt.get("encrypted", [])[0]
					ciphertext = pkt.get("encrypted", [])[1]

					decripted = self.encript.decrypt_message(bytes(nonce), bytes(ciphertext)).decode("utf-8")
					self.messages.append(f"{pkt.get('from')}: {decripted}")
				elif pkt.get("content"):
						self.messages.append(f"{pkt.get('from', 'Anon')}: {pkt.get('content')}")
			except Exception as exc:
				print(exc)

	def connect(self, addr: str, port: int, mssp: int):
		if self.client and self.client.isStarted():
			raise Exception("Client already running")

		self.client = Client(addr, port, "Anon"+str(random.randint(1000, 9999)), mssp)
		self.client.setThread(self._reader)

		self.thread = threading.Thread(target=self.client.start, daemon=True)
		self.thread.start()

	def disconnect(self):
		self.client.stop()
		self.client = None
		self.thread = None
		self.encript = None
		self.encript_enable = False
		return {"status": "ok"}

	def set_username(self, username: str):
		if not self.client:
			raise Exception("Client not connected")
		self.client.setUsername(username)

	def send_message(self, to: str, content: str):
		if not self.client:
			raise Exception("Client not connected")

		if not self.encript_enable:
			pkt = Packet({"to": to, "from": self.client.getUsername(), "content": content})
		else:
			nonce, ciphertext = self.encript.encrypt_message(content.encode("utf-8"))
			pkt = Packet({
				"content": "Encrypted",
				"from": self.client.getUsername(),
				"to": to,
				"encrypted": [list(nonce), list(ciphertext)]
			})

		try:
			self.client.transmit(pkt)
			self.messages.append(f"{self.client.getUsername()}: {content}")
		except Exception as e:
			raise

	def recive_keys(self, to: str, mode: str):
		if not self.client:
			raise Exception("Client not connected")
		pr_k, pub_k = self.encript.generate_keypair()
		key_bytes = self.encript.serialize_public_key()

		self.stoped = True

		if mode == "0":
			pkt = self.client.read()
			if pkt.get("from", "") != to:
				return {"status": "error", "detail": "someone else's key was received, he's: "+pkt.get("from", "Anon")}
			key = bytes(pkt.get("key"))
			self.encript.derive_shared_key(load_public_key(key))

			self.client.send(Packet({"key": list(key_bytes), "to": to, "from": self.client.getUsername()}))
			status = self.client.read()

		elif mode == "1":
			self.client.send(Packet({"key": list(key_bytes), "to": to, "from": self.client.getUsername()}))
			status = self.client.read()

			pkt = self.client.read()
			if pkt.get("from", "") != to:
				return {"status": "error", "detail": "someone else's key was received, he's: "+pkt.get("from", "Anon")}
			key = bytes(pkt.get("key"))
			self.encript.derive_shared_key(load_public_key(key))
		self.stoped = False
		self.encript_enable = True
		
		print(f"Shared key: {self.encript.shared.hex()}")
		return {"status": "ok"}

	def get_messages(self):
		#with self.lock:
		return list(self.messages)


manager = ClientManager()


# Client UI
@app.get("/client")
def client_ui(request: Request):
	return templates.TemplateResponse("client.html", {"request": request})


@app.post("/client/connect")
async def client_connect(payload: dict):
	try:
		addr = payload.get("addr", "127.0.0.1")
		port = int(payload.get("port", 12345))
		mssp = int(payload.get("mssp", 128))
		manager.connect(addr, port, mssp)
		return JSONResponse({"status": "ok"})
	except Exception as e:
		return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.post("/client/disconnect")
async def client_disconnect(payload: dict):
	if payload.get("sure", False):
		return JSONResponse(manager.disconnect())


@app.post("/client/username")
async def client_username(payload: dict):
	try:
		username = payload.get("username")
		manager.set_username(username)
		return JSONResponse({"status": "ok"})
	except Exception as e:
		return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.post("/client/send")
async def client_send(payload: dict):
	try:
		to = payload.get("to", "server")
		content = payload.get("content", "")
		manager.send_message(to, content)
		return JSONResponse({"status": "ok"})
	except Exception as e:
		return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.get("/client/messages")
async def client_messages():
	return JSONResponse(manager.get_messages())


@app.post("/client/keys")
async def client_keys(payload: dict):
	to = payload.get("to", "")
	mode = payload.get("mode", "1")
	if to == "" or to == "server":
		return JSONResponse({"status": "error", "detail": "Getter is null or server"})
	return JSONResponse(manager.recive_keys(to, str(mode)))


# Server UI (simple placeholder)
@app.get("/server")
def server_ui(request: Request):
	return templates.TemplateResponse("server.html", {"request": request})


if __name__ == "__main__":
	import uvicorn

	uvicorn.run(app, host="127.0.0.1", port=8000+random.randint(0, 999))