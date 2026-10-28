from modules.evaluation.confusion import (
    add_outcome,
    confusion_metrics,
    empty_counts,
    merge_counts,
    randomness_detector_confusion,
)


def test_add_outcome_maps_all_four_cells():
    counts = empty_counts()
    add_outcome(counts, True, True)
    add_outcome(counts, True, False)
    add_outcome(counts, False, True)
    add_outcome(counts, False, False)
    assert counts == {"TP": 1, "FN": 1, "FP": 1, "TN": 1}


def test_confusion_metrics_values():
    metrics = confusion_metrics({"TP": 8, "FN": 2, "FP": 1, "TN": 9})
    assert metrics["total"] == 20
    assert metrics["accuracy"] == 17 / 20
    assert metrics["recall"] == 0.8
    assert metrics["specificity"] == 0.9
    assert abs(metrics["precision"] - 8 / 9) < 1e-12


def test_confusion_metrics_handles_empty_counts():
    metrics = confusion_metrics(empty_counts())
    assert metrics["accuracy"] == 0.0 and metrics["f1"] == 0.0


def test_merge_counts():
    merged = merge_counts({"TP": 1, "FN": 0, "FP": 0, "TN": 2}, {"TP": 3, "FN": 1, "FP": 1, "TN": 0})
    assert merged == {"TP": 4, "FN": 1, "FP": 1, "TN": 2}


def test_randomness_detector_separates_defective_from_random():
    result = randomness_detector_confusion(120, 256)
    counts = result["confusion"]
    assert sum(counts.values()) == 240
    assert result["metrics"]["specificity"] >= 0.95
    assert result["metrics"]["recall"] >= 0.9
    assert set(result["per_defect"]) == {"counter", "biased", "periodic", "low_symbol"}