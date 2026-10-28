from Crypto.Hash import SHA256
from Crypto.PublicKey import DSA
from Crypto.Signature import DSS

from .base import BaseCryptoHandler
from .prng import PRNGWrapper


class DSAHandler(BaseCryptoHandler):
    SUPPORTED_KEY_SIZES = (1024, 2048, 3072)
    SIGNATURE_MODE = "deterministic-rfc6979"

    def generate_keypair(self, seed: bytes, key_size: int = 2048) -> tuple:
        self._check_key_size(key_size)
        key = DSA.generate(key_size, randfunc=PRNGWrapper(seed))
        return key, key.publickey()

    def sign(self, private_key, message: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("Message must be bytes")
        signer = DSS.new(private_key, self.SIGNATURE_MODE)
        return signer.sign(SHA256.new(message))

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        if not isinstance(message, bytes) or not isinstance(signature, bytes):
            return False
        try:
            DSS.new(public_key, self.SIGNATURE_MODE).verify(SHA256.new(message), signature)
            return True
        except (ValueError, TypeError):
            return False