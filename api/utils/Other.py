from importlib.util import module_from_spec, spec_from_file_location
import inspect
import json
from pathlib import Path
import socket as socket_module
from cryptography.hazmat.primitives.asymmetric import x25519
import os

def format_bytes(size):
	# Using standard labels instead of binary ones
	for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
		if size < 1024:
			return f"{size:.2f} {unit}"
		size /= 1024
	return f"{size:.2f} EB"


def recv_exact(sock: socket_module.socket, n: int) -> bytes:
	"""Читает из TCP-сокета ровно n байт, дочитывая в цикле.

	TCP не гарантирует, что recv(n) вернёт все n байт за один вызов —
	данные могут прийти по частям (особенно на не-loopback соединениях
	или при больших пакетах). Без этого возможна потеря/обрезка данных.

	Возвращает b"" если соединение было закрыто до получения n байт.
	"""
	if n <= 0:
		return b""
	chunks = []
	remaining = n
	while remaining > 0:
		chunk = sock.recv(remaining)
		if not chunk:
			# Соединение закрыто удалённой стороной
			return b""
		chunks.append(chunk)
		remaining -= len(chunk)
	return b"".join(chunks)


def load_public_key(data: bytes):
	return x25519.X25519PublicKey.from_public_bytes(data)

class Logger:
	logging: bool = True

	def __init__(self):
		self.logging = True

	def setMode(self, mode: bool) -> None:
		self.logging = mode

	def log(self, msg) -> None:
		if not self.logging: return
		print(f"[DM] {msg}")

class FileLogger(Logger):
	file_path: str

	def __init__(self, file_path: str):
		super().__init__()
		self.file_path = file_path

	def log(self, msg) -> None:
		with open(self.file_path, "a") as f:
			f.write(f"[DM] {msg}\n")


class Config:
	def __init__(self, filename):
		self.filename = filename
		self._data = {}

	def get(self, key: str, default):
		return self._data.get(key, default)

	def set(self, key: str, value):
		self._data[key] = value

	def save(self):
		with open(self.filename, 'w') as f:
			json.dump(self._data, f)

	def load(self):
		if not os.path.exists(self.filename):
			return
		with open(self.filename, 'r') as f:
			self._data = json.load(f)

def bytes_to_base64(data: bytes) -> str:
	import base64
	return base64.b64encode(data).decode("utf-8")

def base64_to_bytes(data: str) -> bytes:
	import base64
	return base64.b64decode(data.encode("utf-8"))


def get_all_commands() -> dict:
	s = os.sep
	path_to_cmds = f"{os.getcwd()}{s}api{s}commands{s}client{s}"
	cmds = {}
	for file in Path(path_to_cmds).glob("*.py"):
		if file.name.startswith("_"):
			continue

		cmd_name = file.name.lower().replace("cmd.py", "")

		spec = spec_from_file_location(file.stem, file)

		module = module_from_spec(spec)

		spec.loader.exec_module(module)
		for name, cls in inspect.getmembers(module, inspect.isclass):
			if cls.__module__ == module.__name__:
				cmds[cmd_name] = cls()
	return cmds
			