from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from .base import BaseCryptoHandler
from .prng import PRNGWrapper


class RSAHandler(BaseCryptoHandler):
    SUPPORTED_KEY_SIZES = (1024, 2048, 3072, 4096)
    PUBLIC_EXPONENT = 65537

    def generate_keypair(self, seed: bytes, key_size: int = 2048) -> tuple:
        self._check_key_size(key_size)
        key = RSA.generate(
            key_size,
            randfunc=PRNGWrapper(seed),
            e=self.PUBLIC_EXPONENT,
        )
        return key, key.publickey()

    def sign(self, private_key, message: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("Message must be bytes")
        return pkcs1_15.new(private_key).sign(SHA256.new(message))

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        if not isinstance(message, bytes) or not isinstance(signature, bytes):
            return False
        try:
            pkcs1_15.new(public_key).verify(SHA256.new(message), signature)
            return True
        except (ValueError, TypeError):
            return False