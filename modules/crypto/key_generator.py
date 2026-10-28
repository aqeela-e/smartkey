from .dsa_handler import DSAHandler
from .elgamal_handler import ElGamalHandler
from .prng import derive_seed
from .rsa_handler import RSAHandler

HANDLERS = {
    "RSA": RSAHandler,
    "DSA": DSAHandler,
    "ELGAMAL": ElGamalHandler,
}


class CryptoKeyGenerator:
    def __init__(self, algorithm: str):
        self.algorithm = algorithm.upper()
        if self.algorithm not in HANDLERS:
            raise ValueError(f"Algoritma kriptografi '{algorithm}' tidak didukung.")
        self.handler = HANDLERS[self.algorithm]()

    @property
    def supported_key_sizes(self) -> tuple:
        return self.handler.SUPPORTED_KEY_SIZES

    def derive_seed(self, seed: bytes, key_size: int) -> bytes:
        return derive_seed(seed, self.algorithm, key_size)

    def generate_keys(self, seed: bytes, key_size: int = 2048):
        return self.handler.generate_keypair(self.derive_seed(seed, key_size), key_size)

    def sign(self, private_key, message: bytes) -> bytes:
        return self.handler.sign(private_key, message)

    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        return self.handler.verify(public_key, message, signature)

    def export_public_key(self, public_key):
        if self.algorithm == "ELGAMAL":
            return {
                "p": format(int(public_key.p), "x"),
                "g": format(int(public_key.g), "x"),
                "y": format(int(public_key.y), "x"),
            }
        return public_key.export_key().decode("utf-8")