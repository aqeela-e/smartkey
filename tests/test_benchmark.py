import os
import random
import time

import pytest

from modules.evaluation import benchmark as B


# ---------------------------------------------------------------------------
# Generator tiruan (cepat, tanpa melatih ANN)
# ---------------------------------------------------------------------------
def urandom_arm(name, delay=0.0):
    def f():
        if delay:
            time.sleep(delay)
        return os.urandom(32), {"algorithm": name, "evaluations": 0}
    return f


def bad_arm(name):
    return lambda: (b"\x00" * 32, {"algorithm": name, "evaluations": 0})


def forced_balance_arm(name):
    """Tepat 128 bit '1' dari 256: meniru cacat ANN lama (balance dipaksa)."""
    def f():
        bits = [1] * 128 + [0] * 128
        random.shuffle(bits)
        value = int("".join(map(str, bits)), 2)
        return value.to_bytes(32, "big"), {"algorithm": name, "evaluations": 0}
    return f


# ---------------------------------------------------------------------------
# Statistik dasar (nilai yang dapat diverifikasi dengan tangan)
# ---------------------------------------------------------------------------
def test_wilson_interval_known_values():
    lo, hi = B.wilson_interval(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    lo, hi = B.wilson_interval(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = B.wilson_interval(10, 10)
    assert hi == pytest.approx(1.0) and lo == pytest.approx(0.7225, abs=1e-3)


def test_holm_adjust():
    assert B.holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert B.holm_adjust([0.5]) == [0.5]
    assert all(0.0 <= p <= 1.0 for p in B.holm_adjust([0.9, 0.8, 0.7]))


def test_mde_decreases_with_n():
    assert B.mde_proportion(0.96, 30) > B.mde_proportion(0.96, 100) > B.mde_proportion(0.96, 1000)


# ---------------------------------------------------------------------------
# Budget setara
# ---------------------------------------------------------------------------
def test_budget_matched_params_and_reported_evaluations():
    p = B.budget_matched_params(200)
    ga, aco, ann = p[B.NAME_GA], p[B.NAME_ACO], p[B.NAME_ANN]
    assert aco["num_ants"] * aco["iterations"] == 200
    assert ann["max_attempts"] * (1 + ann["max_refine_steps"]) <= 200
    expected_ga = ga["population_size"] * (1 + 0.76 * ga["generations"])
    assert 0.9 * 200 <= expected_ga <= 1.1 * 200

    gens = B.build_ai_generators(256, 200, 2.0)       # hanya GA & ACO yang dipanggil
    ga_evals = [gens[B.NAME_GA]()[1]["evaluations"] for _ in range(5)]
    aco_evals = [gens[B.NAME_ACO]()[1]["evaluations"] for _ in range(20)]
    assert all(150 <= e <= 230 for e in ga_evals)      # GA memakai ~seluruh budget
    assert all(1 <= e <= 200 for e in aco_evals)       # ACO berhenti dini, tak melebihi batas


# ---------------------------------------------------------------------------
# Logika keputusan
# ---------------------------------------------------------------------------
def _run(arms, n=60, **kw):
    refs = [a for a in arms if a.startswith("REF")]
    return B.run_benchmark(arms, references=refs, n_trials=n, warmup=False, rng_seed=7, **kw)


def test_identical_arms_have_no_statistical_winner_and_pick_fastest():
    arms = {
        "SLOW": urandom_arm("SLOW", delay=0.003),
        "MID": urandom_arm("MID", delay=0.001),
        "FAST": urandom_arm("FAST"),
        "REF1": urandom_arm("REF1"),
        "REF2": urandom_arm("REF2"),
    }
    sel = _run(arms)["selection"]
    assert sel["basis"] == "efficiency_tiebreak"
    assert sel["selected"] == "FAST"
    assert sel["excluded"] == []
    assert "BUKAN karena kualitasnya" in sel["message"]


def test_defective_arm_is_excluded_and_never_selected():
    arms = {"OK": urandom_arm("OK", delay=0.002), "BAD": bad_arm("BAD"),
            "REF1": urandom_arm("REF1"), "REF2": urandom_arm("REF2")}
    sel = _run(arms, n=30)["selection"]
    assert "BAD" in sel["excluded"]
    assert sel["selected"] == "OK"        # BAD lebih cepat, tetapi gugur


def test_all_defective_selects_nothing():
    arms = {"BAD1": bad_arm("BAD1"), "BAD2": bad_arm("BAD2"),
            "REF1": urandom_arm("REF1"), "REF2": urandom_arm("REF2")}
    sel = _run(arms, n=30)["selection"]
    assert sel["selected"] is None and sel["basis"] == "none_eligible"


def test_forced_balance_is_flagged_by_dispersion_diagnostic():
    arms = {"FORCED": forced_balance_arm("FORCED"), "REF1": urandom_arm("REF1"), "REF2": urandom_arm("REF2")}
    rep = _run(arms, n=100)
    s = rep["summary"]["FORCED"]
    assert s["mono_z_std"] < 0.05 and s["mono_z_var_p"] < 1e-6      # keseimbangan dipaksa terlihat
    # Acak sejati: std z ~ 1,0 dengan galat baku ~0,07 pada N=100. Batas dipasang >= 5 galat baku
    # agar tes tidak rapuh (versi awal memakai 0,8 dan gagal ~0,3% dari waktu).
    assert 0.6 < rep["summary"]["REF1"]["mono_z_std"] < 1.5
    # pass/fail saja TIDAK menangkapnya (alasan diagnostik ada). Lengan ini rata-rata lolos ~97,8%
    # (galat baku ~1,5 poin); ambang 0,85 berjarak > 8 galat baku (versi awal 0,95 gagal ~3% waktu).
    assert s["rate_all"] >= 0.85


def test_validation_errors():
    arms = {"A": urandom_arm("A"), "REF1": urandom_arm("REF1")}
    with pytest.raises(ValueError):
        B.run_benchmark(arms, references=["REF1"], n_trials=1)
    with pytest.raises(ValueError):
        B.run_benchmark(arms, references=["NOPE"], n_trials=5)
    with pytest.raises(ValueError):
        B.run_benchmark({"REF1": urandom_arm("REF1")}, references=["REF1"], n_trials=5)


def test_report_tables_shape_and_notes():
    arms = {"A": urandom_arm("A"), "B": urandom_arm("B"), "REF1": urandom_arm("REF1")}
    rep = _run(arms, n=20)
    t = B.report_to_tables(rep)
    assert len(t["summary"]) == 3
    assert len(t["comparison_indep"]) == len(t["comparison_all"]) == 3      # C(3,2) pasangan
    assert any("N < 30" in n for n in rep["notes"])
    assert rep["n_trials"] == 20 and rep["summary"]["A"]["n"] == 20


def test_entropy_source_is_reported_and_insecure_source_is_flagged():
    def arm(name, secure):
        def f():
            return os.urandom(32), {
                "algorithm": name, "evaluations": 0,
                "entropy_source": "os.urandom (CSPRNG)" if secure else "seeded PRNG (TIDAK AMAN, hanya riset/reproduksi)",
                "entropy_source_secure": secure,
            }
        return f

    arms = {"SAFE": arm("SAFE", True), "SEEDED": arm("SEEDED", False), "REF1": urandom_arm("REF1")}
    rep = _run(arms, n=20)
    assert rep["summary"]["SAFE"]["entropy_secure"] is True
    assert rep["summary"]["SEEDED"]["entropy_secure"] is False
    assert rep["summary"]["REF1"]["entropy_secure"] is None              # lengan tanpa laporan sumber
    assert any("PERINGATAN" in n and "SEEDED" in n for n in rep["notes"])
    rows = {r["Algoritma"]: r for r in B.report_to_tables(rep)["summary"]}
    assert rows["SEEDED"]["Sumber acak"].startswith("⚠")
    assert "os.urandom" in rows["SAFE"]["Sumber acak"] and not rows["SAFE"]["Sumber acak"].startswith("⚠")


def test_baseline_arms_report_csprng():
    for name, fn in B.build_baseline_generators(256, 50, 2.0).items():
        _, m = fn()
        assert m["entropy_source_secure"] is True and "os.urandom" in m["entropy_source"]