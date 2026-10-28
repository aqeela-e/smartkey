from typing import List


def penalty_curve(metrics: dict) -> List[float]:
    if metrics.get("convergence_penalty"):
        return [float(v) for v in metrics["convergence_penalty"]]
    history = metrics.get("convergence_history")
    if history:
        return [(1.0 / float(s) - 1.0) if s and s > 0 else 0.0 for s in history]
    return []