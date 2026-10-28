import pytest
from modules.evaluation.entropy import calculate_shannon_entropy, normalize_entropy
from modules.evaluation.nist_tests import run_all_tests
from modules.evaluation.metrics import Evaluator

def test_entropy():
    data = b"\x00" * 10
    assert calculate_shannon_entropy(data) == 0.0
    
    # Random bytes should have high entropy
    import os
    rand_data = os.urandom(100)
    ent = calculate_shannon_entropy(rand_data)
    assert ent > 0.0
    assert normalize_entropy(ent) <= 1.0

def test_nist_tests():
    data = b"\x00\xFF" * 10
    results = run_all_tests(data)
    
    assert "Frequency Test" in results
    assert "Block Frequency Test" in results
    assert "Runs Test" in results

def test_evaluator():
    seed = b"\x00\xFF" * 10
    metrics = {"time_ms": 10.0}
    
    eval_result = Evaluator.evaluate_seed(seed, metrics)
    assert "combined_score" in eval_result
    assert "nist_pass_rate" in eval_result


# ---------------------------------------------------------------------------
# Regresi untuk skala & skor entropi (temuan: dibagi 8 padahal sampel 32 byte)
# ---------------------------------------------------------------------------
import math
import os

from modules.evaluation.entropy import max_entropy_bits, entropy_test, diff_entropy_test


def test_normalize_entropy_uses_sample_bound():
    # Batas seed 32 byte adalah log2(32) = 5 bit, bukan 8.
    assert max_entropy_bits(32) == pytest.approx(5.0)
    assert normalize_entropy(5.0, 32) == pytest.approx(1.0)
    # Perilaku lama (tanpa n_bytes) dipertahankan untuk kompatibilitas.
    assert normalize_entropy(5.0) == pytest.approx(0.625)
    # Sampel >= 256 byte: batas 8 bit.
    assert max_entropy_bits(1024) == pytest.approx(8.0)


def test_entropy_tests_are_calibrated_on_random_data():
    n = 400
    fail_byte = sum(not entropy_test(os.urandom(32))[1] for _ in range(n))
    fail_diff = sum(not diff_entropy_test(os.urandom(32))[1] for _ in range(n))
    # alpha = 1%; toleransi lebar agar tes tidak flaky (batas 5% >> 1% harapan)
    assert fail_byte / n < 0.05
    assert fail_diff / n < 0.05


def test_entropy_tests_detect_structure():
    assert not entropy_test(b"\x55" * 32)[1]            # frekuensi byte timpang
    assert not diff_entropy_test(bytes(range(100, 132)))[1]   # counter: selisih konstan
    assert not diff_entropy_test(bytes((7 * i) % 256 for i in range(32)))[1]


def test_perfect_score_is_attainable_and_not_weighted():
    scores = [Evaluator.evaluate_seed(os.urandom(32), {})["combined_score"] for _ in range(60)]
    assert max(scores) == 1.0                              # skor lama tak pernah lewat ~0,74
    ev = Evaluator.evaluate_seed(bytes(range(100, 132)), {})
    assert ev["combined_score"] < 1.0 and not ev["all_tests_passed"]   # counter tidak lolos penuh
    assert ev["tests_total"] == 5


def test_find_best_configuration_reports_ties():
    a = {"algorithm": "A", "combined_score": 1.0, "time_ms": 50.0}
    b = {"algorithm": "B", "combined_score": 1.0, "time_ms": 5.0}
    c = {"algorithm": "C", "combined_score": 0.8, "time_ms": 1.0}
    best = Evaluator.find_best_configuration([a, b, c])
    assert best["algorithm"] == "B" and set(best["tied_algorithms"]) == {"A", "B"}
    # tanpa seri: pemenang murni berdasar skor, tidak ada tied_algorithms
    best2 = Evaluator.find_best_configuration([a, c])
    assert best2["algorithm"] == "A" and "tied_algorithms" not in best2