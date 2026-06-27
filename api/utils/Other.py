import json

from cryptography.hazmat.primitives.asymmetric import x25519
import os

def format_bytes(size):
	# Using standard labels instead of binary ones
	for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
		if size < 1024:
			return f"{size:.2f} {unit}"
		size /= 1024
	return f"{size:.2f} EB"


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