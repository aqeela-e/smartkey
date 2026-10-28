import os
from typing import Callable, Dict

from .metrics import Evaluator


def empty_counts() -> Dict[str, int]:
    return {"TP": 0, "FN": 0, "FP": 0, "TN": 0}


def add_outcome(counts: Dict[str, int], actual_positive: bool, predicted_positive: bool) -> None:
    if actual_positive:
        counts["TP" if predicted_positive else "FN"] += 1
    else:
        counts["FP" if predicted_positive else "TN"] += 1


def merge_counts(*items: Dict[str, int]) -> Dict[str, int]:
    merged = empty_counts()
    for item in items:
        for key in merged:
            merged[key] += int(item.get(key, 0))
    return merged


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def confusion_metrics(counts: Dict[str, int]) -> Dict[str, float]:
    tp, fn, fp, tn = (counts[k] for k in ("TP", "FN", "FP", "TN"))
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    return {
        "total": tp + fn + fp + tn,
        "accuracy": _ratio(tp + tn, tp + fn + fp + tn),
        "precision": precision,
        "recall": recall,
        "specificity": _ratio(tn, tn + fp),
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def _random_integer(n_bytes: int) -> int:
    return int.from_bytes(os.urandom(n_bytes), "big")


def _counter_seed(n_bytes: int) -> bytes:
    start = _random_integer(1)
    return bytes((start + i) % 256 for i in range(n_bytes))


def _biased_seed(n_bytes: int, p_one: float = 0.7) -> bytes:
    threshold = int(p_one * 256)
    out = 0
    for value in os.urandom(n_bytes * 8):
        out = (out << 1) | (1 if value < threshold else 0)
    return out.to_bytes(n_bytes, "big")


def _periodic_seed(n_bytes: int) -> bytes:
    pattern = os.urandom(2)
    return (pattern * (n_bytes // 2 + 1))[:n_bytes]


def _low_symbol_seed(n_bytes: int) -> bytes:
    symbols = os.urandom(4)
    return bytes(symbols[b & 3] for b in os.urandom(n_bytes))


DEFECTIVE_GENERATORS: Dict[str, Callable[[int], bytes]] = {
    "counter": _counter_seed,
    "biased": _biased_seed,
    "periodic": _periodic_seed,
    "low_symbol": _low_symbol_seed,
}


def randomness_detector_confusion(n_per_class: int, bit_length: int = 256) -> dict:
    if n_per_class < 1:
        raise ValueError("n_per_class minimal 1")
    n_bytes = (bit_length + 7) // 8
    counts = empty_counts()

    for _ in range(n_per_class):
        evaluation = Evaluator.evaluate_seed(os.urandom(n_bytes), {})
        add_outcome(counts, True, bool(evaluation["all_tests_passed"]))

    names = list(DEFECTIVE_GENERATORS)
    per_defect = {name: {"n": 0, "detected": 0} for name in names}
    for i in range(n_per_class):
        name = names[i % len(names)]
        evaluation = Evaluator.evaluate_seed(DEFECTIVE_GENERATORS[name](n_bytes), {})
        passed = bool(evaluation["all_tests_passed"])
        add_outcome(counts, False, passed)
        per_defect[name]["n"] += 1
        per_defect[name]["detected"] += 0 if passed else 1

    return {
        "bit_length": bit_length,
        "n_random": n_per_class,
        "n_defective": n_per_class,
        "confusion": counts,
        "metrics": confusion_metrics(counts),
        "per_defect": per_defect,
    }