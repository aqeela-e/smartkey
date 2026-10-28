from abc import ABC, abstractmethod


class BaseCryptoHandler(ABC):
    SUPPORTED_KEY_SIZES: tuple = ()

    @abstractmethod
    def generate_keypair(self, seed: bytes, key_size: int) -> tuple:
        pass

    @abstractmethod
    def sign(self, private_key, message: bytes) -> bytes:
        pass

    @abstractmethod
    def verify(self, public_key, message: bytes, signature: bytes) -> bool:
        pass

    def _check_key_size(self, key_size: int) -> None:
        if key_size not in self.SUPPORTED_KEY_SIZES:
            raise ValueError(
                "Unsupported key size %s. Choose one of %s."
                % (key_size, self.SUPPORTED_KEY_SIZES)
            )