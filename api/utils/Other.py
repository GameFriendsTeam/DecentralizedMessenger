import asyncio
from importlib.util import module_from_spec, spec_from_file_location
import inspect
import ipaddress
import json
from pathlib import Path
import sys
import threading
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import x25519
import os
from numpy import select


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


ctxs: dict[str, asyncio.AbstractEventLoop] = {}
_threads: dict[str, threading.Thread] = {}
def get_async_ctx(key) -> asyncio.AbstractEventLoop:
	if key not in ctxs:
		ctxs[key] = asyncio.new_event_loop()
		_threads[key] = threading.Thread(target=ctxs[key].run_forever, daemon=True)
		_threads[key].start()
	return ctxs[key]


def run_async_ctx(loop: asyncio.AbstractEventLoop, coro, timeout: Optional[int] = 5.0):
	return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=timeout)


def rm_async_ctx(key) -> None:
	if key in ctxs and key in _threads:
		ctxs[key].stop()
		_threads.get(key).stop()
		del ctxs[key]
		del _threads[key]


def validate_target(address: str):
	import re

	domain_regex = re.compile(r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*$")
	ip_regex = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

	if domain_regex.match(address) or ip_regex.match(address):
		return True
	else:
		return False


async def ainput_unix(prompt: str = "") -> str:
	import tty
	import termios
	if prompt:
		print(prompt, end="", flush=True)
	fd = sys.stdin.fileno()
	old = termios.tcgetattr(fd)
	buf = []
	try:
		tty.setcbreak(fd)
		while True:
			r, _, _ = select.select([sys.stdin], [], [], 0)
			if r:
				ch = sys.stdin.read(1)
				if ch in ("\r", "\n"):
					print()
					return "".join(buf)
				elif ch == "\x7f":
					if buf:
						buf.pop()
						sys.stdout.write("\b \b"); sys.stdout.flush()
				else:
					buf.append(ch)
					sys.stdout.write(ch); sys.stdout.flush()
			else:
				await asyncio.sleep(0.01)
	finally:
		termios.tcsetattr(fd, termios.TCSADRAIN, old)