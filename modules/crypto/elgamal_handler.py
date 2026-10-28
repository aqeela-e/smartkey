import hashlib
import math
import secrets

from Crypto.PublicKey import ElGamal

from .base import BaseCryptoHandler
from .dh_groups import GROUP_GENERATOR, SAFE_PRIME_GROUPS
from .fastmath import invert, powmod
from .prng import PRNGWrapper


class ElGamalHandler(BaseCryptoHandler):
    SUPPORTED_KEY_SIZES = tuple(sorted(SAFE_PRIME_GROUPS))

    def generate_keypair(self, seed: bytes, key_size: int = 2048) -> tuple:
        if not isinstance(seed, bytes) or len(seed) == 0:
            raise ValueError("Seed must be non-empty bytes.")
        self._check_key_size(key_size)
        p = SAFE_PRIME_GROUPS[key_size]
        g = GROUP_GENERATOR
        width = (p.bit_length() + 7) // 8 + 8
        x = int.from_bytes(PRNGWrapper(seed)(width), "big") % (p - 3) + 2
        y = powmod(g, x, p)
        private_key = ElGamal.construct((p, g, y, x))
        return private_key, private_key.publickey()

    @staticmethod
    def _message_integer(message: bytes, p: int) -> int:
        return int.from_bytes(hashlib.sha256(message).digest(), "big") % (p - 1)

    @staticmethod
    def _encode_signature(r: int, s: int, p: int) -> bytes:
        width = (p.bit_length() + 7) // 8
        return r.to_bytes(width, "big") + s.to_bytes(width, "big")

    @staticmethod
    def _decode_signature(signature: bytes, p: int) -> tuple:
        width = (p.bit_length() + 7) // 8
        if not isinstance(signature, bytes) or len(signature) != 2 * width:
            raise ValueError("Invalid signature length.")
        return (
            int.from_bytes(signature[:width], "big"),
            int.from_bytes(signature[width:], "big"),
        )

    def sign(self, private_key, message: bytes) -> bytes:
        if not isinstance(message, bytes):
            raise TypeError("Message must be bytes")
        if not private_key.has_private():
            raise ValueError("A private key is required for signing.")

        p = int(private_key.p)
        g = int(private_key.g)
        x = int(private_key.x)
        m = self._message_integer(message, p)

        while True:
            k = secrets.randbelow(p - 2) + 1
            if math.gcd(k, p - 1) == 1:
                break

        r = powmod(g, k, p)
        s = (invert(k, p - 1) * (m - x * r)) % (p - 1)
        return self._encode_signature(r, s, p)

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        try:
            if not isinstance(message, bytes):
                return False
            p = int(public_key.p)
            g = int(public_key.g)
            y = int(public_key.y)
            r, s = self._decode_signature(signature, p)
            if not (1 <= r < p) or not (0 <= s < p - 1):
                return False
            m = self._message_integer(message, p)
            return powmod(g, m, p) == (powmod(y, r, p) * powmod(r, s, p)) % p
        except (ValueError, TypeError, OverflowError, AttributeError):
            return False