import pytest

from modules.db import Repository


@pytest.fixture()
def repository(tmp_path):
    return Repository(str(tmp_path / "db" / "test.db"))


def test_register_key_is_idempotent_and_findable(repository):
    first = repository.register_key("pem-a", "RSA", 2048, "aa", "bb", "GA")
    again = repository.register_key("pem-a", "RSA", 2048, "aa", "bb", "GA")
    other = repository.register_key("pem-b", "DSA", 2048, "cc", "dd", "ACO")
    assert first == again and other != first
    fingerprint = repository.list_keys()[-1]["fingerprint"]
    assert repository.find_key(fingerprint)["algorithm"] == "RSA"
    assert repository.find_key("missing") is None


def test_results_roundtrip_and_latest(repository):
    first = repository.save_result("experiment", {"a": 1}, "satu")
    second = repository.save_result("experiment", {"a": 2}, "dua")
    repository.save_result("benchmark", {"b": 1}, "bench")
    assert repository.load_result(first) == {"a": 1}
    assert repository.latest_result("experiment") == {"a": 2}
    assert [r["id"] for r in repository.list_results("experiment")] == [second, first]
    assert repository.latest_result("detector") is None
    assert repository.load_result(9999) is None


def test_verification_log(repository):
    repository.add_verification(
        "a.signed.zip",
        {"status": "valid", "reason": "ok", "hash_match": True, "signature_valid": True, "key_registered": None},
    )
    rows = repository.list_verifications()
    assert rows[0]["status"] == "valid" and rows[0]["hash_match"] == 1 and rows[0]["key_registered"] is None


def test_counts(repository):
    counts = repository.counts()
    assert set(counts) == {"keys", "batches", "signed_documents", "verifications", "results"}
    assert all(v == 0 for v in counts.values())