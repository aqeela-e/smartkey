import platform
import statistics
import time
from typing import Callable, Dict, List, Optional, Sequence

import Crypto

from modules.ai import (
    AntColonyOptimizationGenerator,
    GeneticAlgorithmGenerator,
    NeuralNetworkGenerator,
)
from modules.crypto.key_generator import CryptoKeyGenerator
from modules.crypto.prng import DERIVATION_VERSION
from modules.evaluation.confusion import (
    add_outcome,
    confusion_metrics,
    empty_counts,
    merge_counts,
)
from modules.evaluation.convergence import penalty_curve
from modules.evaluation.document_test import (
    TAMPER_MODES,
    evaluate_document,
    group_by_format,
)
from modules.evaluation.metrics import Evaluator

AI_FACTORIES = {
    "GA": GeneticAlgorithmGenerator,
    "ANN": NeuralNetworkGenerator,
    "ACO": AntColonyOptimizationGenerator,
}


def build_ai(name: str):
    if name not in AI_FACTORIES:
        raise ValueError("Algoritma AI tidak dikenal: %s" % name)
    return AI_FACTORIES[name]()


def build_ai_kwargs(
    ai_params: dict,
    bit_length: int,
    tolerance_sigma: float,
    random_state: Optional[int] = None,
) -> dict:
    kwargs = dict(ai_params)
    kwargs["bit_length"] = int(bit_length)
    kwargs["tolerance_sigma"] = float(tolerance_sigma)
    if random_state is not None:
        kwargs["random_state"] = int(random_state)
    return kwargs


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _median(values: Sequence[float]) -> float:
    return statistics.median(values) if values else 0.0


def _seed_quality(evaluations: List[dict]) -> dict:
    n = len(evaluations)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "pass_all": sum(1 for e in evaluations if e["all_tests_passed"]),
        "pass_rate_all": sum(1 for e in evaluations if e["all_tests_passed"]) / n,
        "nist_pass_rate_mean": _mean([e["nist_pass_rate"] for e in evaluations]),
        "entropy_mean": _mean([e["entropy_shannon"] for e in evaluations]),
        "normalized_entropy_mean": _mean([e["normalized_entropy"] for e in evaluations]),
        "min_p_value_mean": _mean([e["min_p_value"] for e in evaluations]),
        "ai_time_ms_mean": _mean([e.get("time_ms", 0.0) for e in evaluations]),
    }


def run_experiment(
    documents: Sequence[tuple],
    ai_name: str,
    ai_kwargs: dict,
    key_sizes: Dict[str, int],
    n_trials: int,
    tamper_modes: Sequence[str] = TAMPER_MODES,
    limit_per_format: Optional[int] = None,
    random_state_base: Optional[int] = None,
    progress: Optional[Callable[[float], None]] = None,
) -> dict:
    if n_trials < 1:
        raise ValueError("n_trials minimal 1")
    groups = group_by_format(documents, limit_per_format)
    if not groups:
        raise ValueError("Tidak ada dokumen dengan format yang didukung")
    algorithms = list(key_sizes)
    generator = build_ai(ai_name)

    total_steps = n_trials * len(algorithms) * sum(len(v) for v in groups.values())
    done = 0

    counts = {a: empty_counts() for a in algorithms}
    counts_by_format = {a: {f: empty_counts() for f in groups} for a in algorithms}
    counts_by_mode = {a: {m: empty_counts() for m in tamper_modes} for a in algorithms}
    keygen_ms = {a: [] for a in algorithms}
    sign_ms = {a: [] for a in algorithms}
    verify_ms = {a: [] for a in algorithms}
    signature_bytes = {a: 0 for a in algorithms}
    trials: List[dict] = []
    evaluations: List[dict] = []

    for t in range(n_trials):
        kwargs = dict(ai_kwargs)
        if random_state_base is not None:
            kwargs["random_state"] = int(random_state_base) + t
        seed, ai_metrics = generator.generate(**kwargs)
        evaluation = Evaluator.evaluate_seed(seed, ai_metrics)
        evaluations.append(evaluation)

        trial = {
            "trial": t + 1,
            "seed_hex": seed.hex(),
            "convergence_penalty": penalty_curve(ai_metrics),
            "evaluation": evaluation,
            "algorithms": {},
        }

        for algorithm in algorithms:
            crypto_gen = CryptoKeyGenerator(algorithm)
            start = time.perf_counter()
            private_key, public_key = crypto_gen.generate_keys(seed, key_sizes[algorithm])
            elapsed = (time.perf_counter() - start) * 1000
            keygen_ms[algorithm].append(elapsed)
            trial["algorithms"][algorithm] = {
                "key_size": key_sizes[algorithm],
                "derived_seed_hex": crypto_gen.derive_seed(seed, key_sizes[algorithm]).hex(),
                "keygen_ms": elapsed,
                "public_key": crypto_gen.export_public_key(public_key),
            }

            for label, docs in groups.items():
                for _, data in docs:
                    outcome = evaluate_document(
                        crypto_gen, private_key, public_key, data, tamper_modes
                    )
                    sign_ms[algorithm].append(outcome["sign_ms"])
                    verify_ms[algorithm].append(outcome["verify_ms"])
                    signature_bytes[algorithm] = outcome["signature_bytes"]

                    add_outcome(counts[algorithm], True, outcome["original_valid"])
                    add_outcome(counts_by_format[algorithm][label], True, outcome["original_valid"])
                    for mode, valid in outcome["tampered_valid"].items():
                        add_outcome(counts[algorithm], False, valid)
                        add_outcome(counts_by_format[algorithm][label], False, valid)
                        add_outcome(counts_by_mode[algorithm][mode], False, valid)

                    done += 1
                    if progress and (done % 25 == 0 or done == total_steps):
                        progress(min(1.0, done / total_steps))

        trials.append(trial)

    summary = {}
    for algorithm in algorithms:
        summary[algorithm] = {
            "key_size": key_sizes[algorithm],
            "confusion": counts[algorithm],
            "metrics": confusion_metrics(counts[algorithm]),
            "by_format": {
                f: {"confusion": c, "metrics": confusion_metrics(c)}
                for f, c in counts_by_format[algorithm].items()
            },
            "by_tamper_mode": {
                m: {"confusion": c, "metrics": confusion_metrics(c)}
                for m, c in counts_by_mode[algorithm].items()
            },
            "timing": {
                "keygen_ms_mean": _mean(keygen_ms[algorithm]),
                "keygen_ms_median": _median(keygen_ms[algorithm]),
                "sign_ms_mean": _mean(sign_ms[algorithm]),
                "sign_ms_median": _median(sign_ms[algorithm]),
                "verify_ms_mean": _mean(verify_ms[algorithm]),
                "verify_ms_median": _median(verify_ms[algorithm]),
            },
            "signature_bytes": signature_bytes[algorithm],
        }

    overall = merge_counts(*counts.values())
    return {
        "kind": "experiment",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": {
            "python": platform.python_version(),
            "pycryptodome": Crypto.__version__,
            "seed_derivation": DERIVATION_VERSION,
        },
        "config": {
            "ai": ai_name,
            "ai_kwargs": ai_kwargs,
            "key_sizes": key_sizes,
            "n_trials": n_trials,
            "tamper_modes": list(tamper_modes),
            "limit_per_format": limit_per_format,
            "random_state_base": random_state_base,
            "shared_seed_per_trial": True,
        },
        "documents": {
            "total": sum(len(v) for v in groups.values()),
            "per_format": {f: len(v) for f, v in groups.items()},
        },
        "verification_confusion": overall,
        "verification_metrics": confusion_metrics(overall),
        "summary": summary,
        "seed_quality": _seed_quality(evaluations),
        "trials": trials,
    }