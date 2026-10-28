import pytest

from modules.evaluation.document_test import (
    TAMPER_MODES,
    format_of,
    group_by_format,
    load_folder,
    synthetic_documents,
    tamper,
)
from modules.experiment import build_ai_kwargs, list_results, run_experiment, save_result, to_json
from modules.evaluation.convergence import penalty_curve
from modules.experiment.runner import build_ai


@pytest.mark.parametrize("mode", TAMPER_MODES)
def test_tamper_always_changes_data(mode):
    for data in (b"", b"a", b"hello world" * 10):
        assert tamper(data, mode) != data


def test_tamper_is_deterministic_and_rejects_unknown_mode():
    assert tamper(b"abcdef", "flip_bit") == tamper(b"abcdef", "flip_bit")
    with pytest.raises(ValueError):
        tamper(b"abc", "unknown")


def test_format_detection_and_grouping():
    assert format_of("a.PDF") == "PDF"
    assert format_of("a.jpeg") == "JPG"
    assert format_of("a.xyz") is None
    docs = synthetic_documents(4)
    groups = group_by_format(docs, limit_per_format=3)
    assert all(len(v) == 3 for v in groups.values())
    assert set(groups) == {"PDF", "DOCX", "TXT", "PNG", "JPG"}


def test_load_folder_respects_limit(tmp_path):
    for i in range(5):
        (tmp_path / ("f%d.txt" % i)).write_bytes(b"data%d" % i)
    (tmp_path / "ignored.bin").write_bytes(b"x")
    assert len(load_folder(str(tmp_path), 3)) == 3
    with pytest.raises(FileNotFoundError):
        load_folder(str(tmp_path / "missing"))


@pytest.fixture(scope="module")
def result():
    kwargs = build_ai_kwargs({"num_ants": 8, "iterations": 5}, 256, 2.0)
    return run_experiment(
        synthetic_documents(4),
        "ACO",
        kwargs,
        {"RSA": 1024, "DSA": 1024},
        n_trials=2,
        random_state_base=7,
    )


def test_experiment_confusion_counts_are_consistent(result):
    docs = result["documents"]["total"]
    for data in result["summary"].values():
        counts = data["confusion"]
        assert counts["TP"] == docs * 2
        assert counts["TN"] == docs * 2 * len(TAMPER_MODES)
        assert counts["FP"] == 0 and counts["FN"] == 0
        assert data["metrics"]["accuracy"] == 1.0


def test_experiment_shares_one_seed_per_trial_with_separated_derivation(result):
    for trial in result["trials"]:
        derived = {a: d["derived_seed_hex"] for a, d in trial["algorithms"].items()}
        assert len(set(derived.values())) == len(derived)
        assert trial["seed_hex"]


def test_experiment_is_reproducible_with_random_state(result):
    kwargs = build_ai_kwargs({"num_ants": 8, "iterations": 5}, 256, 2.0)
    again = run_experiment(
        synthetic_documents(2), "ACO", kwargs, {"RSA": 1024}, n_trials=2, random_state_base=7
    )
    assert [t["seed_hex"] for t in again["trials"]] == [t["seed_hex"] for t in result["trials"]]
    assert result["trials"][0]["seed_hex"] != result["trials"][1]["seed_hex"]


def test_experiment_records_timing_and_environment(result):
    for data in result["summary"].values():
        timing = data["timing"]
        assert timing["keygen_ms_mean"] > 0 and timing["sign_ms_mean"] > 0 and timing["verify_ms_mean"] > 0
    assert result["config"]["shared_seed_per_trial"] is True
    assert result["environment"]["pycryptodome"]


def test_result_is_json_serializable_and_persisted(result, tmp_path):
    assert "seed_hex" in to_json(result)
    path = save_result(result, "experiment", str(tmp_path))
    assert path.endswith(".json")
    assert len(list_results(str(tmp_path))) == 1


def test_run_experiment_validation():
    kwargs = build_ai_kwargs({}, 128, 2.0)
    with pytest.raises(ValueError):
        run_experiment(synthetic_documents(1), "ACO", kwargs, {"RSA": 1024}, n_trials=0)
    with pytest.raises(ValueError):
        run_experiment([("a.unknown", b"x")], "ACO", kwargs, {"RSA": 1024}, n_trials=1)


@pytest.mark.parametrize("name,params", [("GA", {"population_size": 10, "generations": 5}), ("ANN", {"hidden_layers": (10,)}), ("ACO", {"num_ants": 5, "iterations": 5})])
def test_every_ai_exposes_a_convergence_curve(name, params):
    _, metrics = build_ai(name).generate(**build_ai_kwargs(params, 128, 2.0))
    assert len(penalty_curve(metrics)) >= 1