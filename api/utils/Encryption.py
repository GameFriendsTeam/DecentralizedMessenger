from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519, ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidSignature
from cryptography.fernet import Fernet
import os
import hashlib
import base64
import json
import time


class Encryption:
	def __init__(self):
		...

	def generate_keypair(self):
		self.private_key = x25519.X25519PrivateKey.generate()
		self.public_key = self.private_key.public_key()
		return self.private_key, self.public_key

	def serialize_public_key(self):
		return self.public_key.public_bytes(
			encoding=serialization.Encoding.Raw,
			format=serialization.PublicFormat.Raw
		)

	def derive_shared_key(self, peer_public_key):
		shared_secret = self.private_key.exchange(peer_public_key)

		hkdf = HKDF(
			algorithm=hashes.SHA256(),
			length=32,  # 256 бит для AES-256
			salt=None,
			info=b"e2ee-chat",
		)
		self.shared = hkdf.derive(shared_secret)
		return self.shared


	def encrypt_message(self, plaintext: bytes):
		aesgcm = AESGCM(self.shared)
		nonce = os.urandom(12)  # 96 бит — стандарт для GCM
		ciphertext = aesgcm.encrypt(nonce, plaintext, None)
		return nonce, ciphertext

	def decrypt_message(self, nonce: bytes, ciphertext: bytes):
		aesgcm = AESGCM(self.shared)
		return aesgcm.decrypt(nonce, ciphertext, None)


class FileEncryption:
	def __init__(self, key = None):
		self.key = Fernet.generate_key()

		if key != None:
			self.key = key
		self._f = Fernet(self.key)

	def getKey(self):
		return self.key

	def encrypt(self, filepath):
		with open(filepath, "rb") as file:
			file_data = file.read()
		encrypted_data = self._f.encrypt(file_data)
		return encrypted_data
		
	def decrypt(self, data):
		return self._f.decrypt(data)


class SecurityError(Exception):
	"""Ошибка безопасности"""
	pass

class SecureEncryption:
	def __init__(self, username: str):
		self.username = username

		self.x25519_private = None
		self.x25519_public = None

		self.ed25519_private = None
		self.ed25519_public = None

		self.shared = None

		self.trusted_keys = self._load_trusted_keys()

	def _load_trusted_keys(self):
		try:
			os.makedirs("keys", exist_ok=True)
			with open(f"keys/.trusted_keys_{self.username}.json", "r") as f:
				return json.load(f)
		except FileNotFoundError:
			return {}

	def _save_trusted_keys(self):
		os.makedirs("keys", exist_ok=True)
		with open(f"keys/.trusted_keys_{self.username}.json", "w") as f:
			json.dump(self.trusted_keys, f)
	
	def generate_keypair(self):
		self.x25519_private = x25519.X25519PrivateKey.generate()
		self.x25519_public = self.x25519_private.public_key()
		return self.x25519_private, self.x25519_public
	
	def generate_signing_keypair(self):
		self.ed25519_private = ed25519.Ed25519PrivateKey.generate()
		self.ed25519_public = self.ed25519_private.public_key()
		return self.ed25519_private, self.ed25519_public
	
	def serialize_x25519_public(self):
		return self.x25519_public.public_bytes(
			encoding=serialization.Encoding.Raw,
			format=serialization.PublicFormat.Raw
		)
	
	def serialize_ed25519_public(self):
		return self.ed25519_public.public_bytes(
			encoding=serialization.Encoding.Raw,
			format=serialization.PublicFormat.Raw
		)
	
	def sign_message(self, message: bytes) -> bytes:
		return self.ed25519_private.sign(message)
	
	def verify_signature(self, message: bytes, signature: bytes, 
						peer_ed25519_public_bytes: bytes) -> bool:
		try:
			peer_public = ed25519.Ed25519PublicKey.from_public_bytes(
				peer_ed25519_public_bytes
			)
			peer_public.verify(signature, message)
			return True
		except InvalidSignature:
			return False
	
	def get_fingerprint(self, key_bytes: bytes) -> str:
		fingerprint = hashlib.sha256(key_bytes).hexdigest()[:32].upper()
		return ' '.join([fingerprint[i:i+4] for i in range(0, 32, 4)])
	
	def derive_shared_key(self, peer_x25519_public):
		shared_secret = self.x25519_private.exchange(peer_x25519_public)
		
		hkdf = HKDF(
			algorithm=hashes.SHA256(),
			length=32,
			salt=None,
			info=b"secure-chat-v1",
		)
		self.shared = hkdf.derive(shared_secret)
		return self.shared
	
	def encrypt_message(self, plaintext: bytes):
		if not self.shared:
			raise SecurityError("Shared key not established")
		
		aesgcm = AESGCM(self.shared)
		nonce = os.urandom(12)
		ciphertext = aesgcm.encrypt(nonce, plaintext, None)
		return nonce, ciphertext
	
	def decrypt_message(self, nonce: bytes, ciphertext: bytes):
		if not self.shared:
			raise SecurityError("Shared key not established")
		
		aesgcm = AESGCM(self.shared)
		return aesgcm.decrypt(nonce, ciphertext, None)
	
	def verify_peer_manually(self, peer_username: str, 
							peer_ed25519_public_bytes: bytes,
							peer_x25519_public_bytes: bytes = None):
		print(f"\n Verification of key by {peer_username}")
		print("-" * 40)
		
		my_fingerprint = self.get_fingerprint(self.serialize_ed25519_public())
		peer_fingerprint = self.get_fingerprint(peer_ed25519_public_bytes)
		
		print(f"You're fingerprint:	{my_fingerprint}")
		print(f"Fingerprint {peer_username}: {peer_fingerprint}")
		print("-" * 40)
		
		print("\nСравните отпечатки через защищенный канал:")
		
		response = input("\nОтпечатки совпадают? (yes/no): ").lower()
		
		if response == 'yes':
			self.trusted_keys[peer_username] = {
				"ed25519_public": base64.b64encode(peer_ed25519_public_bytes).decode(),
				"fingerprint": peer_fingerprint,
				"verified_at": int(time.time())
			}
			if peer_x25519_public_bytes:
				self.trusted_keys[peer_username]["x25519_public"] = \
					base64.b64encode(peer_x25519_public_bytes).decode()
			self._save_trusted_keys()
			print("Ключ верифицирован и сохранен")
			return True
		else:
			print("Верификация отменена")
			return False
	
	def get_trusted_peer_key(self, peer_username: str):
		if peer_username in self.trusted_keys:
			key_data = self.trusted_keys[peer_username]
			return {
				"ed25519_public": base64.b64decode(key_data["ed25519_public"]),
				"x25519_public": base64.b64decode(key_data.get("x25519_public", b"")),
				"fingerprint": key_data["fingerprint"]
			}
		return None