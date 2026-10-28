from typing import List, Dict

from .entropy import (
    calculate_shannon_entropy,
    normalize_entropy,
    max_entropy_bits,
    entropy_test,
    diff_entropy_test,
)
from .nist_tests import run_all_tests


class Evaluator:
    """
    Evaluates the generated keys (seeds) from AI models.

    Baterai uji (semua memakai konvensi yang sama: p-value, lolos bila p >= 0,01):
      1. Uji entropi-byte terkalibrasi pada panjang sampel (entropy.py)
      2. Uji entropi selisih antar-byte (menangkap counter/deret aritmetika)
      3. NIST Frequency (Monobit)
      4. NIST Block Frequency
      5. NIST Runs

    `combined_score` = fraksi tes yang lulus (bobot sama, tanpa bobot arbitrer).
    Skala 0..1 dan 1.0 BISA dicapai. Data acak sejati mendapat 1.0 sekitar 95%
    dari waktu (5 tes berpeluang gagal-palsu ~1% masing-masing), jadi skor ini
    adalah uji lulus/gagal, BUKAN peringkat kualitas: dua seed yang sama-sama
    lulus tidak bisa dikatakan lebih baik satu dari yang lain dari satu sampel.
    """

    @staticmethod
    def evaluate_seed(seed_bytes: bytes, ai_metrics: dict) -> dict:
        """
        Takes a seed and the time metrics from AI generation,
        runs the test battery and returns the evaluation.
        """
        n_bytes = len(seed_bytes)

        entropy = calculate_shannon_entropy(seed_bytes)
        entropy_max = max_entropy_bits(n_bytes)
        norm_entropy = normalize_entropy(entropy, n_bytes)
        entropy_p, entropy_passed = entropy_test(seed_bytes)
        diff_p, diff_passed = diff_entropy_test(seed_bytes)

        nist_results = run_all_tests(seed_bytes)

        nist_total = len(nist_results)
        nist_passed = sum(
            1 for res in nist_results.values() if res["passed"]
        )
        nist_pass_rate = (
            nist_passed / nist_total if nist_total > 0 else 0.0
        )

        tests_total = nist_total + 2
        tests_passed = (
            nist_passed + (1 if entropy_passed else 0) + (1 if diff_passed else 0)
        )
        combined_score = tests_passed / tests_total

        p_values = [res["p_value"] for res in nist_results.values()] + [entropy_p, diff_p]

        evaluation = {
            "entropy_shannon": entropy,
            "entropy_max_bits": entropy_max,
            "normalized_entropy": norm_entropy,
            "entropy_p_value": entropy_p,
            "entropy_passed": entropy_passed,
            "diff_entropy_p_value": diff_p,
            "diff_entropy_passed": diff_passed,
            "nist_results": nist_results,
            "nist_pass_rate": nist_pass_rate,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "all_tests_passed": tests_passed == tests_total,
            "min_p_value": min(p_values),
            "combined_score": combined_score,
            **ai_metrics,
        }

        return evaluation

    @staticmethod
    def find_best_configuration(evaluations: List[Dict]) -> dict:
        """
        Memilih evaluasi dengan `combined_score` tertinggi.

        Karena skor kini berupa fraksi tes lulus, seri adalah hal yang umum.
        Seri diselesaikan dengan waktu generate terendah (kriteria kedua yang
        eksplisit; BUKAN klaim bahwa pemenangnya lebih berkualitas). Algoritma
        yang seri dicatat di kunci `tied_algorithms`.

        PERINGATAN: ini BUKAN perbandingan algoritma yang valid. Satu sampel per
        algoritma tidak punya kekuatan statistik, budget tidak setara, dan tanpa
        baseline. Fungsi ini dipertahankan hanya untuk kompatibilitas dan sebagai
        pemecah seri sederhana. Untuk membandingkan algoritma gunakan
        `modules.evaluation.benchmark.run_benchmark` (percobaan berulang, budget
        setara, baseline, uji statistik).
        """
        if not evaluations:
            return {}

        top = max(e["combined_score"] for e in evaluations)
        tied = [e for e in evaluations if abs(e["combined_score"] - top) < 1e-12]
        best = dict(min(tied, key=lambda e: e.get("time_ms", float("inf"))))
        if len(tied) > 1:
            best["tied_algorithms"] = [e.get("algorithm", "?") for e in tied]
        return best