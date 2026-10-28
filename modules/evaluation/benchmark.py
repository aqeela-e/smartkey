import math
import os
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

from scipy.stats import chi2, fisher_exact, norm

from ..ai.base import randomness_penalty
from .metrics import Evaluator
from .nist_tests import bytes_to_bits

_Z975 = 1.959963984540054
GeneratorFn = Callable[[], Tuple[bytes, dict]]

NAME_GA = "GA"
NAME_ANN = "ANN"
NAME_ACO = "ACO"
NAME_URANDOM = "Baseline: os.urandom"
NAME_REJECTION = "Baseline: rejection sampling (tanpa AI)"

def wilson_interval(k: int, n: int, z: float = _Z975) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)

def holm_adjust(p_values: List[float]) -> List[float]:
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[i]))
        adjusted[i] = running
    return adjusted

def mde_proportion(p0: float, n: int, alpha: float = 0.05, power: float = 0.8) -> float:
    if n <= 0:
        return 1.0
    p0 = min(max(p0, 0.05), 0.95)
    return (norm.ppf(1 - alpha / 2.0) + norm.ppf(power)) * math.sqrt(2.0 * p0 * (1.0 - p0) / n)

def _fisher_p(k1: int, n1: int, k2: int, n2: int) -> float:
    return float(fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative="two-sided")[1])

def budget_matched_params(budget: int = 200, ann_hidden: tuple = (10,)) -> Dict[str, dict]:
    pop = 20
    gens = max(1, int(round((budget - pop) / (0.76 * pop))))
    attempts = 3
    return {
        NAME_GA: dict(population_size=pop, generations=gens),
        NAME_ACO: dict(num_ants=10, iterations=max(1, budget // 10)),
        NAME_ANN: dict(
            hidden_layers=tuple(ann_hidden),
            max_attempts=attempts,
            max_refine_steps=max(1, budget // attempts - 1),
        ),
    }

def build_ai_generators(
    bit_length: int = 256,
    budget: int = 200,
    tolerance_sigma: float = 2.0,
    ann_hidden: tuple = (10,),
) -> Dict[str, GeneratorFn]:
    from ..ai import (
        GeneticAlgorithmGenerator,
        NeuralNetworkGenerator,
        AntColonyOptimizationGenerator,
    )

    params = budget_matched_params(budget, ann_hidden)
    ga, ann, aco = (
        GeneticAlgorithmGenerator(),
        NeuralNetworkGenerator(),
        AntColonyOptimizationGenerator(),
    )

    def make(gen, kw):
        return lambda: gen.generate(bit_length=bit_length, tolerance_sigma=tolerance_sigma, **kw)

    return {
        NAME_GA: make(ga, params[NAME_GA]),
        NAME_ANN: make(ann, params[NAME_ANN]),
        NAME_ACO: make(aco, params[NAME_ACO]),
    }

def _random_value(bit_length: int) -> int:
    nbytes = (bit_length + 7) // 8
    return int.from_bytes(os.urandom(nbytes), "big") >> (nbytes * 8 - bit_length)

def _value_to_bytes(value: int, bit_length: int) -> bytes:
    return value.to_bytes((bit_length + 7) // 8, "big")

def build_baseline_generators(
    bit_length: int = 256, budget: int = 200, tolerance_sigma: float = 2.0
) -> Dict[str, GeneratorFn]:

    def urandom_fn():
        return _value_to_bytes(_random_value(bit_length), bit_length), {
            "algorithm": NAME_URANDOM,
            "evaluations": 0,
            "entropy_source": "os.urandom (CSPRNG)",
            "entropy_source_secure": True,
        }

    def rejection_fn():
        best_value, best_pen, used = None, float("inf"), 0
        for _ in range(budget):
            value = _random_value(bit_length)
            bits = [int(c) for c in bin(value)[2:].zfill(bit_length)]
            pen = randomness_penalty(bits, tolerance_sigma=tolerance_sigma)
            used += 1
            if pen < best_pen:
                best_value, best_pen = value, pen
            if pen == 0:
                break
        return _value_to_bytes(best_value, bit_length), {
            "algorithm": NAME_REJECTION,
            "evaluations": used,
            "entropy_source": "os.urandom (CSPRNG)",
            "entropy_source_secure": True,
        }

    return {NAME_URANDOM: urandom_fn, NAME_REJECTION: rejection_fn}

def _trial_record(seed: bytes, ev: dict, wall_ms: float) -> dict:
    nist = ev["nist_results"]
    bits = bytes_to_bits(seed)
    n = len(bits)
    return {
        "all_pass": bool(ev["all_tests_passed"]),
        "indep_pass": bool(ev["entropy_passed"] and ev["diff_entropy_passed"]),
        "entropy_pass": bool(ev["entropy_passed"]),
        "diff_pass": bool(ev["diff_entropy_passed"]),
        "freq_pass": bool(nist["Frequency Test"]["passed"]),
        "block_pass": bool(nist["Block Frequency Test"]["passed"]),
        "runs_pass": bool(nist["Runs Test"]["passed"]),
        "tests_passed": int(ev["tests_passed"]),
        "time_ms": float(wall_ms),
        "evaluations": ev.get("evaluations"),
        "mono_z": (2.0 * sum(bits) - n) / math.sqrt(n) if n else 0.0,
        "entropy_source": ev.get("entropy_source"),
        "entropy_secure": ev.get("entropy_source_secure"),
    }

def _percentile(values: List[float], q: float) -> float:
    s = sorted(values)
    if not s:
        return 0.0
    pos = (len(s) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)

def _summarize(records: List[dict], seeds: List[bytes]) -> dict:
    n = len(records)
    k_all = sum(r["all_pass"] for r in records)
    k_ind = sum(r["indep_pass"] for r in records)
    lo_a, hi_a = wilson_interval(k_all, n)
    lo_i, hi_i = wilson_interval(k_ind, n)
    times = [r["time_ms"] for r in records]
    evals = [r["evaluations"] for r in records if r["evaluations"] is not None]
    zs = [r["mono_z"] for r in records]
    mean_z = sum(zs) / n if n else 0.0
    z_var = sum((z - mean_z) ** 2 for z in zs) / (n - 1) if n > 1 else 0.0
    z_std = math.sqrt(z_var)

    if n > 2:
        stat = (n - 1) * z_var
        z_var_p = float(min(1.0, 2.0 * min(chi2.cdf(stat, n - 1), chi2.sf(stat, n - 1))))
    else:
        z_var_p = 1.0

    def fail_rate(key):
        return sum(not r[key] for r in records) / n if n else 0.0

    sources = sorted({r["entropy_source"] for r in records if r.get("entropy_source")})
    flags = [r["entropy_secure"] for r in records if r.get("entropy_secure") is not None]

    return {
        "n": n,
        "k_all": k_all,
        "rate_all": k_all / n if n else 0.0,
        "ci_all": (lo_a, hi_a),
        "k_indep": k_ind,
        "rate_indep": k_ind / n if n else 0.0,
        "ci_indep": (lo_i, hi_i),
        "fail_rates": {
            "Entropi-byte": fail_rate("entropy_pass"),
            "Entropi selisih": fail_rate("diff_pass"),
            "NIST Frequency": fail_rate("freq_pass"),
            "NIST Block Freq": fail_rate("block_pass"),
            "NIST Runs": fail_rate("runs_pass"),
        },
        "mean_tests_passed": sum(r["tests_passed"] for r in records) / n if n else 0.0,
        "time_ms_median": _percentile(times, 0.5),
        "time_ms_mean": sum(times) / n if n else 0.0,
        "time_ms_p90": _percentile(times, 0.9),
        "evaluations_mean": (sum(evals) / len(evals)) if evals else None,
        "evaluations_max": max(evals) if evals else None,
        "distinct_seeds": len(set(seeds)),

        "mono_z_std": z_std,
        "mono_z_var_p": z_var_p,

        "entropy_source": ", ".join(sources) if sources else "-",
        "entropy_secure": (all(flags) if flags else None),
    }

def _pairwise(summary: Dict[str, dict], rate_key: str, k_key: str, alpha: float) -> List[dict]:
    names = list(summary)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]
    raw = [
        _fisher_p(summary[a][k_key], summary[a]["n"], summary[b][k_key], summary[b]["n"])
        for a, b in pairs
    ]
    adj = holm_adjust(raw)
    rows = []
    for (a, b), p_raw, p_adj in zip(pairs, raw, adj):
        ra, rb = summary[a][rate_key], summary[b][rate_key]
        if p_adj < alpha and ra != rb:
            verdict = "%s lebih baik" % (a if ra > rb else b)
        else:
            verdict = "tidak berbeda signifikan"
        rows.append({
            "a": a, "b": b, "rate_a": ra, "rate_b": rb,
            "p_raw": p_raw, "p_holm": p_adj, "verdict": verdict,
            "significant": bool(p_adj < alpha and ra != rb),
            "better": (a if ra > rb else b) if (p_adj < alpha and ra != rb) else None,
        })
    return rows

def _sig_better(comparisons: List[dict], x: str, y: str) -> bool:
    for row in comparisons:
        if {row["a"], row["b"]} == {x, y}:
            return row["better"] == x
    return False

def select_algorithm(report: dict) -> dict:
    cands = report["candidates"]
    refs = report["references"]
    summary = report["summary"]
    cmp_all = report["comparisons"]["all"]
    cmp_ind = report["comparisons"]["indep"]
    n = report["n_trials"]

    excluded = [
        c for c in cands
        if any(_sig_better(cmp_all, r, c) or _sig_better(cmp_ind, r, c) for r in refs)
    ]
    eligible = [c for c in cands if c not in excluded]

    winners = [
        c for c in eligible
        if all(_sig_better(cmp_ind, c, o) for o in cands if o != c)
    ]

    pooled = sum(summary[a]["k_all"] for a in summary) / max(1, sum(summary[a]["n"] for a in summary))
    mde = mde_proportion(pooled, n)
    power_note = (
        "Dengan %d percobaan per algoritma, perbedaan tingkat-lolos yang lebih kecil dari "
        "sekitar %.0f poin persentase tidak dapat dideteksi secara andal (daya 80%%, α=0,05)."
        % (n, mde * 100)
    )

    if winners:
        selected, basis = winners[0], "statistical_winner"
        message = (
            "%s lebih baik secara signifikan daripada algoritma AI lain pada uji yang tidak "
            "dioptimasi (α=0,05, koreksi Holm)." % selected
        )
    elif eligible:
        selected = min(eligible, key=lambda c: summary[c]["time_ms_median"])
        basis = "efficiency_tiebreak"
        message = (
            "Tidak ada pemenang statistik: perbedaan kualitas antar algoritma tidak signifikan "
            "pada %d percobaan. %s dipilih berdasarkan efisiensi (median waktu terendah), "
            "BUKAN karena kualitasnya lebih baik." % (n, selected)
        )
    else:
        selected, basis = None, "none_eligible"
        message = (
            "Semua algoritma AI signifikan lebih buruk daripada baseline. Tidak ada yang dipilih."
        )

    return {
        "selected": selected,
        "basis": basis,
        "excluded": excluded,
        "eligible": eligible,
        "message": message,
        "power_note": power_note,
        "mde_points": mde * 100,
    }

def run_benchmark(
    generators: Dict[str, GeneratorFn],
    references: List[str],
    n_trials: int = 30,
    alpha: float = 0.05,
    warmup: bool = True,
    rng_seed: Optional[int] = None,
    progress: Optional[Callable[[float], None]] = None,
) -> dict:
    if n_trials < 2:
        raise ValueError("n_trials minimal 2")
    unknown = [r for r in references if r not in generators]
    if unknown:
        raise ValueError("referensi tidak dikenal: %s" % unknown)

    names = list(generators)
    candidates = [n for n in names if n not in references]
    if not candidates:
        raise ValueError("tidak ada kandidat (semua lengan adalah referensi)")

    warmup_ms: Dict[str, float] = {}
    if warmup:
        for name in names:
            t0 = time.perf_counter()
            generators[name]()
            warmup_ms[name] = (time.perf_counter() - t0) * 1000.0

    order_rng = random.Random(rng_seed)
    records: Dict[str, List[dict]] = {n: [] for n in names}
    seeds: Dict[str, List[bytes]] = {n: [] for n in names}

    for t in range(n_trials):
        order = names[:]
        order_rng.shuffle(order)
        for name in order:
            t0 = time.perf_counter()
            seed, metrics = generators[name]()
            wall_ms = (time.perf_counter() - t0) * 1000.0
            ev = Evaluator.evaluate_seed(seed, metrics)
            records[name].append(_trial_record(seed, ev, wall_ms))
            seeds[name].append(seed)
        if progress:
            progress((t + 1) / n_trials)

    summary = {n: _summarize(records[n], seeds[n]) for n in names}
    report = {
        "n_trials": n_trials,
        "alpha": alpha,
        "arms": names,
        "candidates": candidates,
        "references": list(references),
        "summary": summary,
        "seeds": {n: [x.hex() for x in seeds[n]] for n in names},
        "warmup_ms": warmup_ms,
        "comparisons": {
            "all": _pairwise(summary, "rate_all", "k_all", alpha),
            "indep": _pairwise(summary, "rate_indep", "k_indep", alpha),
        },
        "notes": [
            "Uji independen = entropi-byte dan entropi selisih (tidak dioptimasi oleh generator).",
            "Uji NIST tumpang-tindih dengan kriteria penyaringan generator (sirkular): "
            "dipakai sebagai syarat gugur, bukan bukti keunggulan.",
        ],
    }
    if n_trials < 30:
        report["notes"].append("N < 30: daya statistik sangat rendah; hasil hanya indikatif.")
    insecure = [n for n in names if summary[n]["entropy_secure"] is False]
    if insecure:
        report["notes"].append(
            "PERINGATAN: lengan %s memakai PRNG ber-seed (tidak aman). Hanya untuk riset/reproduksi; "
            "jangan dipakai membangkitkan kunci sesungguhnya." % ", ".join(insecure)
        )
    ref_rates = [summary[r]["rate_indep"] for r in references]
    if ref_rates and min(ref_rates) >= 0.9:
        report["notes"].append(
            "Efek langit-langit: baseline acak sejati sudah lolos uji independen %.0f%%, sehingga "
            "keunggulan kualitas sangat sulit dibuktikan (uji simulasi: generator yang sempurna pun "
            "baru terdeteksi andal pada N sekitar 1000). Hasil umumnya jatuh ke kriteria efisiensi."
            % (100 * min(ref_rates))
        )
    report["selection"] = select_algorithm(report)
    return report

def report_to_tables(report: dict) -> Dict[str, List[dict]]:
    summary_rows = []
    for name in report["arms"]:
        s = report["summary"][name]
        fr = s["fail_rates"]
        ev_txt = "-"
        if s["evaluations_mean"] is not None:
            ev_txt = "%.1f (maks %d)" % (s["evaluations_mean"], s["evaluations_max"])
        summary_rows.append({
            "Algoritma": name,
            "N": s["n"],
            "Lolos semua tes": "%d/%d (%.1f%%)" % (s["k_all"], s["n"], 100 * s["rate_all"]),
            "CI 95% (Wilson)": "%.1f%% - %.1f%%" % (100 * s["ci_all"][0], 100 * s["ci_all"][1]),
            "Lolos uji independen": "%d/%d (%.1f%%)" % (s["k_indep"], s["n"], 100 * s["rate_indep"]),
            "Gagal (%): entropi/selisih/freq/blok/runs": " / ".join(
                "%.0f" % (100 * fr[k]) for k in
                ("Entropi-byte", "Entropi selisih", "NIST Frequency", "NIST Block Freq", "NIST Runs")
            ),
            "Waktu median (ms)": "%.2f" % s["time_ms_median"],
            "Evaluasi rata-rata": ev_txt,
            "Seed unik": "%d/%d" % (s["distinct_seeds"], s["n"]),
            "Std z-monobit (acak=1,0)": "%.2f (p=%.3f)" % (s["mono_z_std"], s["mono_z_var_p"]),
            "Sumber acak": (
                ("⚠ " if s["entropy_secure"] is False else "") + s["entropy_source"]
            ),
        })

    def cmp_rows(key):
        return [{
            "Perbandingan": "%s vs %s" % (r["a"], r["b"]),
            "Tingkat A": "%.1f%%" % (100 * r["rate_a"]),
            "Tingkat B": "%.1f%%" % (100 * r["rate_b"]),
            "p (Holm)": "%.4f" % r["p_holm"],
            "Kesimpulan": r["verdict"],
        } for r in report["comparisons"][key]]

    return {
        "summary": summary_rows,
        "comparison_indep": cmp_rows("indep"),
        "comparison_all": cmp_rows("all"),
    }