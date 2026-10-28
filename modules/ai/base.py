from abc import ABC, abstractmethod
from typing import Sequence, Tuple
import math
import time
import os


class AIKeyGenerator(ABC):
    """
    Base class for all AI key generators.
    """

    @abstractmethod
    def generate(self, bit_length: int, **kwargs) -> Tuple[bytes, dict]:
        """
        Generate a random bit string (seed) of specified length.

        Args:
            bit_length (int): Length of the bit string to generate.
            **kwargs: Additional parameters for the specific AI algorithm.

        Returns:
            Tuple[bytes, dict]: A tuple containing:
                - seed (bytes): The generated bit string as bytes.
                - metrics (dict): Metrics such as 'time_ms', 'entropy'
                  (if calculated inside), 'iterations', etc.
        """
        pass

    def bit_string_to_bytes(self, bit_string: str) -> bytes:
        """Helper to convert a string of '0's and '1's to bytes."""
        return int(bit_string, 2).to_bytes(
            (len(bit_string) + 7) // 8,
            byteorder="big"
        )


def randomness_penalty(
    bits: Sequence[int],
    tolerance_sigma: float = 2.0,
    block_size: int = 8,
    max_lag: int = 8,
) -> float:
    """
    Penalti deviasi statistik sebuah bit-string dari keacakan ideal.
    0.0 = seluruh statistik berada dalam zona toleransi (lolos).

    Statistik yang diperiksa (semuanya z-score terhadap distribusi bit i.i.d. adil):
      1. Monobit: selisih jumlah '1' dari n/2.
      2. Autokorelasi lag 1..max_lag: jumlah pasangan bit sama pada jarak lag.
         (lag 1 setara dengan Runs Test.)
      3. Block frequency (chi-kuadrat, blok `block_size` bit).

    Desain penting: penalti hanya dihitung untuk |z| > tolerance_sigma
    (zona toleransi). Fungsi ini sengaja BUKAN skor "makin besar makin acak":
    skor seperti itu mendorong seleksi ke pola terlalu sempurna/terstruktur
    (mis. 0101... atau tepat 50% satu). Di dalam zona toleransi semua kandidat
    setara, sehingga seleksi hanya menolak string yang jelas menyimpang
    dan tidak mengarahkan ke pola tertentu.
    """
    n = len(bits)
    if n < 2:
        return 0.0

    s = "".join("1" if b else "0" for b in bits)
    x = int(s, 2)
    zs = []

    # 1. Monobit
    zs.append((s.count("1") - n / 2.0) / (math.sqrt(n) / 2.0))

    # 2. Autokorelasi lag 1..max_lag
    for lag in range(1, min(max_lag, n - 1) + 1):
        m = n - lag
        diff = (x ^ (x >> lag)) & ((1 << m) - 1)
        agree = m - bin(diff).count("1")
        zs.append((agree - m / 2.0) / (math.sqrt(m) / 2.0))

    # 3. Block frequency
    n_blocks = n // block_size
    if n_blocks >= 1:
        chi = 0.0
        for b in range(n_blocks):
            pi = s[b * block_size:(b + 1) * block_size].count("1") / block_size
            chi += (pi - 0.5) ** 2
        chi *= 4.0 * block_size
        zs.append((chi - n_blocks) / math.sqrt(2.0 * n_blocks))

    return sum(max(0.0, abs(z) - tolerance_sigma) ** 2 for z in zs)