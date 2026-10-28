import hashlib
import hmac

DERIVATION_VERSION = "v1"


class PRNGWrapper:
    def __init__(self, seed: bytes):
        if not isinstance(seed, bytes):
            raise TypeError("Seed must be bytes")
        if len(seed) == 0:
            raise ValueError("Seed must not be empty")
        self.state = seed

    def __call__(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("Requested byte length must be non-negative")
        result = bytearray()
        while len(result) < n:
            self.state = hashlib.sha256(self.state).digest()
            result.extend(self.state)
        return bytes(result[:n])


def derive_seed(raw_seed: bytes, algorithm: str, key_size: int) -> bytes:
    if not isinstance(raw_seed, bytes) or len(raw_seed) == 0:
        raise ValueError("Raw seed must be non-empty bytes")
    label = "SmartKey|%s|%s|%d" % (DERIVATION_VERSION, algorithm.upper(), int(key_size))
    return hmac.new(raw_seed, label.encode("utf-8"), hashlib.sha256).digest()