import math
from typing import Optional, Tuple

import numpy as np

# Cache distribusi nol (null) entropi per panjang sampel. Dibangkitkan dengan
# generator ber-seed tetap sehingga p-value deterministik antar proses.
_NULL_CACHE: dict = {}


def calculate_shannon_entropy(data: bytes) -> float:
    """
    Shannon entropy (plug-in) dari frekuensi byte, dalam bit per byte.

    PENTING: nilai ini dibatasi oleh ukuran sampel. Untuk n byte, nilai
    maksimumnya adalah log2(min(256, n)), BUKAN 8. Seed 32 byte paling tinggi
    5,0 bit/byte. Lihat `max_entropy_bits`.
    """
    if not data:
        return 0.0

    entropy = 0.0
    length = len(data)

    # Count frequencies of each byte
    counts = np.zeros(256, dtype=int)
    for byte in data:
        counts[byte] += 1

    for count in counts:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)

    return entropy


def max_entropy_bits(n_bytes: int) -> float:
    """
    Batas atas teoritis entropi plug-in untuk sampel n byte:
    log2(min(256, n)). Tercapai bila semua byte berbeda (n <= 256) atau
    terdistribusi merata (n >= 256).
    """
    if n_bytes <= 1:
        return 0.0
    return math.log2(min(256, n_bytes))


def normalize_entropy(entropy: float, n_bytes: Optional[int] = None) -> float:
    """
    Menormalkan entropi ke skala 0.0 - 1.0 terhadap batas yang BISA dicapai.

    * n_bytes diberikan : dibagi log2(min(256, n_bytes)). Inilah penggunaan
      yang benar untuk sampel berukuran terbatas (mis. seed 32 byte).
    * n_bytes = None    : dibagi 8,0 (perilaku lama; hanya valid untuk sampel
      >= ~ribuan byte). Dipertahankan agar pemanggil lama tidak rusak.
    """
    if n_bytes is None:
        return entropy / 8.0
    limit = max_entropy_bits(n_bytes)
    if limit <= 0.0:
        return 0.0
    return min(1.0, entropy / limit)


def _rows_entropy(X: np.ndarray, n_symbols: int) -> np.ndarray:
    """Entropi plug-in (bit/simbol) untuk tiap baris X (nilai 0..255)."""
    n_sim = X.shape[0]
    idx = X + 256 * np.arange(n_sim)[:, None]
    counts = np.bincount(idx.ravel(), minlength=n_sim * 256).reshape(n_sim, 256)
    p = counts / float(n_symbols)
    with np.errstate(divide="ignore", invalid="ignore"):
        terms = np.where(p > 0, p * np.log2(p), 0.0)
    return -terms.sum(axis=1)


def _entropy_null_distribution(n_bytes: int, mode: str = "byte") -> np.ndarray:
    """
    Distribusi entropi plug-in untuk n byte i.i.d. seragam (hipotesis nol),
    diestimasi dengan Monte Carlo (seed tetap -> deterministik), dan di-cache.

    mode="byte": entropi frekuensi byte.
    mode="diff": entropi selisih antar-byte (b[i+1]-b[i]) mod 256, disimulasikan
                 dari proses yang sebenarnya (selisih berurutan saling bergantung,
                 jadi bukan sekadar n-1 sampel i.i.d.).
    """
    key = (n_bytes, mode)
    cached = _NULL_CACHE.get(key)
    if cached is not None:
        return cached

    n_sim = int(min(10000, max(2000, 4_000_000 // max(n_bytes, 1))))
    rng = np.random.default_rng(1_000_003 + n_bytes + (7919 if mode == "diff" else 0))
    X = rng.integers(0, 256, size=(n_sim, n_bytes))
    if mode == "diff":
        D = (X[:, 1:] - X[:, :-1]) % 256
        null = np.sort(_rows_entropy(D, n_bytes - 1))
    else:
        null = np.sort(_rows_entropy(X, n_bytes))

    _NULL_CACHE[key] = null
    return null


def _lower_tail_p(null: np.ndarray, observed: float) -> float:
    # jumlah null <= observed (toleransi numerik), koreksi +1 agar p tidak pernah 0
    k = int(np.searchsorted(null, observed + 1e-9, side="right"))
    return float(min(1.0, (k + 1.0) / (len(null) + 1.0)))


def entropy_test(data: bytes, alpha: float = 0.01) -> Tuple[float, bool]:
    """
    Uji entropi-byte satu sisi (sisi rendah), terkalibrasi pada panjang sampel.

    H0: data adalah n byte i.i.d. seragam. p-value = P(entropi <= teramati | H0),
    diestimasi dari distribusi nol Monte Carlo. Lolos bila p >= alpha, sama
    seperti konvensi uji NIST di nist_tests.py (alpha = 0,01).

    Batasan: uji ini hanya mendeteksi frekuensi byte yang timpang/berulang.
    Ia TIDAK mendeteksi urutan terprediksi yang semua byte-nya berbeda
    (mis. 0,1,2,...,31). Untuk itu lihat `diff_entropy_test`.
    """
    n = len(data)
    if n == 0:
        return 0.0, False
    if n == 1:
        return 1.0, True

    p_value = _lower_tail_p(_entropy_null_distribution(n, "byte"), calculate_shannon_entropy(data))
    return p_value, bool(p_value >= alpha)


def diff_entropy_test(data: bytes, alpha: float = 0.01) -> Tuple[float, bool]:
    """
    Uji entropi selisih antar-byte (sisi rendah), terkalibrasi pada panjang sampel.

    Menghitung entropi dari d[i] = (b[i+1] - b[i]) mod 256. Deret aritmetika
    (counter 0,1,2,..., kelipatan konstan) menghasilkan selisih konstan sehingga
    entropinya nol, walau entropi frekuensi byte-nya maksimum.

    Batasan jujur: hanya menangkap struktur selisih. Struktur lain yang tampak
    acak secara statistik (mis. SHA-256 dari sebuah counter) tidak terdeteksi
    oleh uji statistik mana pun pada satu sampel pendek.
    """
    n = len(data)
    if n < 3:
        return 1.0, True

    arr = np.frombuffer(bytes(data), dtype=np.uint8).astype(np.int64)
    d = (arr[1:] - arr[:-1]) % 256
    obs = float(_rows_entropy(d[None, :], n - 1)[0])
    p_value = _lower_tail_p(_entropy_null_distribution(n, "diff"), obs)
    return p_value, bool(p_value >= alpha)