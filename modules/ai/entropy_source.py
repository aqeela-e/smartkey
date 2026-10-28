"""
Sumber keacakan untuk modul AI (GA, ACO, ANN): satu-satunya "pintu" entropi.

Mengapa ada modul ini
---------------------
Seed kunci kriptografi harus berasal dari sumber acak yang aman secara
kriptografis (CSPRNG). Versi sebelumnya memakai `random` dan `np.random`
(Mersenne Twister, MT19937) yang BUKAN CSPRNG: seluruh keluarannya ditentukan
oleh state internal 19.937 bit, dan state itu dapat dipulihkan dari 624 keluaran
32-bit yang berurutan. Algoritma AI hanya mentransformasi keluaran PRNG
(seleksi, perbaikan bit); AI tidak menambah entropi. Karena itu kualitas
entropi seed ditentukan sepenuhnya oleh sumber acak di bawahnya.

Aturan
------
* Default (`random_state=None`): semua keacakan berasal dari `os.urandom`
  (CSPRNG sistem operasi). Seluruh pemanggilan lewat modul ini, sehingga dapat
  diaudit dan diuji (lihat tests/test_entropy_source.py).
* `random_state=<int>`: PRNG ber-seed yang deterministik, HANYA untuk
  riset/reproduksi eksperimen dan pengujian. Hasilnya TIDAK AMAN untuk kunci
  sesungguhnya. Sumber ini menandai dirinya `secure = False` dan metrik hasil
  mencantumkannya.
* `os.urandom` sengaja dipanggil lewat atribut modul `os` pada saat pemanggilan
  (bukan alias yang diikat saat impor) agar pengujian dapat membuktikan bahwa
  seluruh keacakan benar-benar mengalir lewat sini.
"""

import os
from typing import Optional

import numpy as np

_TWO_POW_53 = float(1 << 53)


class EntropySource:
    """Antarmuka sumber acak yang dipakai GA, ACO, dan ANN."""

    name = "abstract"
    secure = False

    def uniform(self, n: int) -> np.ndarray:
        """n bilangan float64 seragam di [0, 1)."""
        raise NotImplementedError

    def bits(self, n: int) -> np.ndarray:
        """n bit seragam (uint8 bernilai 0/1)."""
        raise NotImplementedError

    def randbelow(self, n: int) -> int:
        """Bilangan bulat seragam di [0, n), tanpa bias modulo."""
        raise NotImplementedError

    def normal(self, n: int) -> np.ndarray:
        """n sampel N(0, 1) (Box-Muller dari uniform)."""
        m = (int(n) + 1) // 2
        u1 = 1.0 - self.uniform(m)          # (0, 1], menghindari log(0)
        u2 = self.uniform(m)
        r = np.sqrt(-2.0 * np.log(u1))
        theta = 2.0 * np.pi * u2
        return np.concatenate([r * np.cos(theta), r * np.sin(theta)])[: int(n)]

    # Kenyamanan -----------------------------------------------------------
    def random(self) -> float:
        return float(self.uniform(1)[0])

    def randint(self, a: int, b: int) -> int:
        """Bilangan bulat seragam di [a, b] (kedua ujung inklusif)."""
        return a + self.randbelow(b - a + 1)


class SystemEntropySource(EntropySource):
    """CSPRNG: seluruh keacakan dari `os.urandom`."""

    name = "os.urandom (CSPRNG)"
    secure = True

    def uniform(self, n: int) -> np.ndarray:
        n = int(n)
        if n <= 0:
            return np.empty(0, dtype=np.float64)
        raw = np.frombuffer(os.urandom(8 * n), dtype="<u8")
        return (raw >> np.uint64(11)).astype(np.float64) / _TWO_POW_53

    def bits(self, n: int) -> np.ndarray:
        n = int(n)
        if n <= 0:
            return np.empty(0, dtype=np.uint8)
        raw = np.frombuffer(os.urandom((n + 7) // 8), dtype=np.uint8)
        return np.unpackbits(raw)[:n]

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("randbelow membutuhkan n > 0")
        if n == 1:
            return 0
        k = (n - 1).bit_length()
        nbytes = (k + 7) // 8
        shift = nbytes * 8 - k
        while True:                      # pengambilan-ulang: seragam tanpa bias
            r = int.from_bytes(os.urandom(nbytes), "big") >> shift
            if r < n:
                return r


class SeededEntropySource(EntropySource):
    """
    PRNG deterministik ber-seed (NumPy PCG64). HANYA untuk riset/reproduksi dan
    pengujian. TIDAK AMAN untuk membangkitkan kunci sesungguhnya.
    """

    name = "seeded PRNG (TIDAK AMAN, hanya riset/reproduksi)"
    secure = False

    def __init__(self, seed: int):
        self._rng = np.random.default_rng(int(seed))

    def uniform(self, n: int) -> np.ndarray:
        return self._rng.random(int(n))

    def bits(self, n: int) -> np.ndarray:
        return self._rng.integers(0, 2, int(n), dtype=np.uint8)

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("randbelow membutuhkan n > 0")
        return int(self._rng.integers(0, n))

    def normal(self, n: int) -> np.ndarray:
        return self._rng.standard_normal(int(n))


def get_entropy_source(random_state: Optional[int] = None) -> EntropySource:
    """CSPRNG bila `random_state` None; PRNG ber-seed (tidak aman) bila diberikan."""
    if random_state is None:
        return SystemEntropySource()
    return SeededEntropySource(random_state)