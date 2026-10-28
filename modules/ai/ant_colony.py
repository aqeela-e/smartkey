import math
import time
from typing import List, Optional, Tuple

from .base import AIKeyGenerator, randomness_penalty
from .entropy_source import get_entropy_source

# Parameter internal (bukan slider UI)
_MAX_LAG = 8          # lag autokorelasi yang dipantau heuristik (sama dengan randomness_penalty)
_MIN_PREFIX = 16      # jumlah observasi minimum sebelum z-score parsial dipercaya
_TAU_RATIO = 20.0     # tau_max / tau_min  (MMAS) -> peluang minimum satu bit = 1/21 (~4,8%)


class AntColonyOptimizationGenerator(AIKeyGenerator):
    """
    Generate seeds using Ant Colony Optimization (varian MAX-MIN Ant System).

    Graf konstruksi: node (posisi, bit). Semut membangun jalur bit demi bit;
    peluang memilih bit b pada posisi i:

        P(b | i)  ∝  tau[i][b]^alpha  *  eta(b | prefix)^beta

    * tau (feromon)  : memori kolektif koloni tentang pilihan bit yang
                       menghasilkan jalur berskor baik.
    * eta (heuristik): informasi lokal yang bergantung pada awalan jalur.
                       Netral (=1) selama statistik awalan (monobit dan
                       autokorelasi lag 1..8) masih di dalam zona toleransi;
                       jika statistik awalan sudah keluar zona, bit yang
                       menarik statistik kembali ke zona diberi bobot lebih.
                       Heuristik sengaja TIDAK memberi hadiah pada
                       "makin seimbang/makin sering berganti", sehingga tidak
                       mendorong pola terstruktur.
    * `beta` kini dipakai (beta=0 mematikan heuristik, alpha=0 mematikan feromon).

    Pembaruan feromon (MMAS):
      1. Evaporasi:  tau <- (1 - rho) * tau
      2. Deposit hanya oleh semut terbaik iterasi dan semut terbaik global
         (sebesar skornya) -> sinyal selektif, bukan semua semut.
      3. Batas: tau dijepit ke [tau_min, tau_max], tau_max = best_score / rho,
         agar koloni tidak terkunci dan eksplorasi tetap ada.

    Skor jalur = 1 / (1 + penalti), penalti dari `randomness_penalty` (base.py).
    Skor 1.0 berarti jalur lolos semua pemeriksaan (zona toleransi). Karena
    skor jenuh di 1.0, pencarian berhenti begitu ada jalur berskor 1.0
    (`early_stop=True`), sehingga tidak ada tekanan seleksi tambahan setelah
    syarat terpenuhi.

    Sumber acak: semua keputusan acak (pemilihan bit tiap semut) berasal dari
    `os.urandom` (CSPRNG) lewat `entropy_source.py`. Dengan `random_state=<int>`
    dipakai PRNG ber-seed yang TIDAK AMAN, hanya untuk riset/reproduksi.

    Catatan: seleksi pada output mempersempit distribusi output; zona
    toleransi menjaga penyempitan itu minimal. ACO tidak dapat menghasilkan
    string yang lebih acak daripada sumber acaknya.
    """

    def _evaluate_path(self, path: List[int], tolerance_sigma: float = 2.0) -> float:
        """
        Skor jalur dalam (0, 1]. 1.0 = seluruh statistik dalam zona toleransi.
        """
        return 1.0 / (1.0 + randomness_penalty(path, tolerance_sigma=tolerance_sigma))

    def generate(
        self,
        bit_length: int,
        num_ants: int = 10,
        iterations: int = 20,
        evaporation_rate: float = 0.1,
        alpha: float = 1.0,
        beta: float = 1.0,
        tolerance_sigma: float = 2.0,
        early_stop: bool = True,
        random_state: Optional[int] = None,
        **kwargs
    ) -> Tuple[bytes, dict]:

        if bit_length < 1 or num_ants < 1 or iterations < 1:
            raise ValueError("bit_length, num_ants, dan iterations harus >= 1")

        start_time = time.perf_counter()
        source = get_entropy_source(random_state)

        rho = min(max(float(evaporation_rate), 1e-3), 1.0)
        tol = float(tolerance_sigma)

        # Tabel 1/sqrt(m) untuk z-score parsial: z = (2*count - m) / sqrt(m)
        inv_sqrt = [0.0] + [1.0 / math.sqrt(m) for m in range(1, bit_length + 2)]

        # Feromon awal = tau_max awal (MMAS): eksplorasi maksimal di awal
        tau_max = 1.0 / rho
        tau_min = tau_max / _TAU_RATIO
        pheromones = [[tau_max, tau_max] for _ in range(bit_length)]

        best_path: List[int] = []
        best_score = -1.0
        history: List[float] = []
        evaluations = 0
        iterations_run = 0
        use_heuristic = beta != 0 and bit_length > _MIN_PREFIX

        for _ in range(iterations):
            iterations_run += 1
            # Pangkat alpha dihitung sekali per iterasi
            tau_a = [(t[0] ** alpha, t[1] ** alpha) for t in pheromones]

            iter_best_path: List[int] = []
            iter_best_score = -1.0
            stop = False

            for _ant in range(num_ants):
                path: List[int] = []
                ones = 0
                # Seluruh bilangan acak semut ini diambil dalam satu panggilan CSPRNG
                u_ant = source.uniform(bit_length).tolist()
                agree = [0] * (_MAX_LAG + 1)  # agree[k]: pasangan (j, j+k) yang bitnya sama

                for i in range(bit_length):
                    w0, w1 = tau_a[i]

                    if use_heuristic and i >= _MIN_PREFIX:
                        v0 = v1 = 0.0
                        # Monobit parsial
                        z = (2 * ones - i) * inv_sqrt[i]
                        if z > tol:
                            v0 += z - tol          # terlalu banyak '1' -> condong ke 0
                        elif z < -tol:
                            v1 += -z - tol         # terlalu sedikit '1' -> condong ke 1
                        # Autokorelasi parsial lag 1..8
                        for k in range(1, _MAX_LAG + 1):
                            m = i - k
                            if m < _MIN_PREFIX:
                                break
                            z = (2 * agree[k] - m) * inv_sqrt[m]
                            if z > tol:            # terlalu sering sama -> pilih beda
                                if path[i - k]:
                                    v0 += z - tol
                                else:
                                    v1 += z - tol
                            elif z < -tol:         # terlalu sering beda -> pilih sama
                                if path[i - k]:
                                    v1 += -z - tol
                                else:
                                    v0 += -z - tol
                        if v0:
                            w0 *= (1.0 + v0) ** beta
                        if v1:
                            w1 *= (1.0 + v1) ** beta

                    bit = 1 if u_ant[i] < (w1 / (w0 + w1)) else 0

                    for k in range(1, _MAX_LAG + 1):
                        if i < k:
                            break
                        if bit == path[i - k]:
                            agree[k] += 1
                    ones += bit
                    path.append(bit)

                score = self._evaluate_path(path, tol)
                evaluations += 1

                if score > iter_best_score:
                    iter_best_score = score
                    iter_best_path = path
                if score > best_score:
                    best_score = score
                    best_path = path[:]

                if early_stop and best_score >= 1.0:
                    stop = True
                    break

            history.append(best_score)
            if stop:
                break

            # --- Pembaruan feromon (MMAS) ---
            tau_max = best_score / rho
            tau_min = tau_max / _TAU_RATIO

            for i in range(bit_length):
                pheromones[i][0] *= 1.0 - rho
                pheromones[i][1] *= 1.0 - rho

            # Deposit: semut terbaik iterasi dan semut terbaik global
            for dep_path, dep_score in ((iter_best_path, iter_best_score),
                                        (best_path, best_score)):
                for i, bit in enumerate(dep_path):
                    pheromones[i][bit] += dep_score

            for i in range(bit_length):
                for b in (0, 1):
                    if pheromones[i][b] > tau_max:
                        pheromones[i][b] = tau_max
                    elif pheromones[i][b] < tau_min:
                        pheromones[i][b] = tau_min

        bit_string = "".join(str(bit) for bit in best_path)
        seed_bytes = self.bit_string_to_bytes(bit_string)

        end_time = time.perf_counter()

        metrics = {
            "algorithm": "Ant Colony Optimization (ACO)",
            "time_ms": (end_time - start_time) * 1000,
            "num_ants": num_ants,
            "iterations": iterations,
            "iterations_run": iterations_run,
            "evaluations": evaluations,
            "evaporation_rate": evaporation_rate,
            "alpha": alpha,
            "beta": beta,
            "best_score": best_score,
            "best_penalty": (1.0 / best_score) - 1.0,
            "converged": best_score >= 1.0,
            "convergence_history": history,
            "tolerance_sigma": tolerance_sigma,
            "entropy_source": source.name,
            "entropy_source_secure": source.secure,
        }

        return seed_bytes, metrics