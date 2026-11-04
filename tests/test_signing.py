import io
import json
import os
import zipfile

import pytest

from modules.db import Repository
from modules.evaluation.document_test import synthetic_documents
from modules.experiment.runner import build_ai_kwargs
from modules.signing import (
    PACKAGE_SUFFIX,
    STATUS_INVALID,
    STATUS_UNSIGNED,
    STATUS_VALID,
    build_package,
    check_signature,
    expand_uploads,
    read_package,
    sign_documents,
    verify_package,
)
from modules.signing.package import (
    DOCUMENT_DIR,
    REASON_BAD_PACKAGE,
    REASON_MODIFIED,
    REASON_OK,
    REASON_SIGNATURE,
    REASON_UNSIGNED,
)

AI_KWARGS = build_ai_kwargs({"num_ants": 6, "iterations": 5}, 256, 2.0)


@pytest.fixture()
def repository(tmp_path):
    return Repository(str(tmp_path / "test.db"))


def signed_batch(repository, tmp_path, count=4, algorithm="RSA", size=1024):
    documents = synthetic_documents(1)[:count]
    result = sign_documents(
        documents, "ACO", AI_KWARGS, algorithm, size, repository, str(tmp_path / "packages")
    )
    return documents, result


def rewrite_member(package_bytes, member, new_content):
    source = zipfile.ZipFile(io.BytesIO(package_bytes))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as target:
        for info in source.infolist():
            content = new_content if info.filename == member else source.read(info.filename)
            target.writestr(info.filename, content)
    return buffer.getvalue()


def test_single_document_package_differs_from_original_and_verifies(repository, tmp_path):
    documents, result = signed_batch(repository, tmp_path, count=1)
    assert result["kind"] == "single"
    assert result["package_path"].endswith(PACKAGE_SUFFIX)
    package_bytes = open(result["package_path"], "rb").read()
    assert package_bytes != documents[0][1]
    outcome = verify_package(package_bytes, repository.find_key)
    assert outcome["status"] == STATUS_VALID
    assert outcome["reason"] == REASON_OK
    assert outcome["key_registered"] is True


def test_unsigned_file_is_reported_unsigned(repository):
    outcome = verify_package(b"dokumen biasa yang belum ditandatangani", repository.find_key)
    assert outcome["status"] == STATUS_UNSIGNED
    assert outcome["reason"] == REASON_UNSIGNED


def test_modified_document_inside_package_is_invalid(repository, tmp_path):
    documents, result = signed_batch(repository, tmp_path, count=1)
    package_bytes = open(result["package_path"], "rb").read()
    name = documents[0][0]
    altered = rewrite_member(package_bytes, DOCUMENT_DIR + name, documents[0][1] + b"x")
    outcome = verify_package(altered, repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_MODIFIED


def test_corrupted_signature_is_invalid(repository, tmp_path):
    _, result = signed_batch(repository, tmp_path, count=1)
    package_bytes = open(result["package_path"], "rb").read()
    signature = bytearray(read_package(package_bytes)["signature"])
    signature[0] ^= 0x01
    altered = rewrite_member(package_bytes, "signature.sig", bytes(signature))
    outcome = verify_package(altered, repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_SIGNATURE


def test_broken_manifest_is_bad_package(repository, tmp_path):
    _, result = signed_batch(repository, tmp_path, count=1)
    package_bytes = open(result["package_path"], "rb").read()
    altered = rewrite_member(package_bytes, "manifest.json", json.dumps({"x": 1}))
    outcome = verify_package(altered, repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_BAD_PACKAGE


def test_unregistered_key_is_flagged(tmp_path, repository):
    documents, result = signed_batch(repository, tmp_path, count=1)
    package_bytes = open(result["package_path"], "rb").read()
    other = Repository(str(tmp_path / "other.db"))
    outcome = verify_package(package_bytes, other.find_key)
    assert outcome["status"] == STATUS_VALID
    assert outcome["key_registered"] is False


@pytest.mark.parametrize("algorithm,size", [("RSA", 1024), ("DSA", 1024), ("ElGamal", 2048)])
def test_batch_zip_contains_every_signed_package(repository, tmp_path, algorithm, size):
    documents, result = signed_batch(repository, tmp_path, count=5, algorithm=algorithm, size=size)
    assert result["kind"] == "batch"
    archive = zipfile.ZipFile(result["package_path"])
    packages = [n for n in archive.namelist() if n.endswith(PACKAGE_SUFFIX)]
    assert len(packages) == 5
    assert "index.csv" in archive.namelist()
    expanded = expand_uploads("batch.zip", open(result["package_path"], "rb").read())
    assert len(expanded) == 5
    for _, data in expanded:
        assert verify_package(data, repository.find_key)["status"] == STATUS_VALID


def test_batch_records_are_stored_in_database(repository, tmp_path):
    documents, result = signed_batch(repository, tmp_path, count=3)
    batch = repository.get_batch(result["batch_id"])
    assert batch["doc_count"] == 3 and os.path.exists(batch["package_path"])
    rows = repository.list_signed_documents(result["batch_id"])
    assert [r["name"] for r in rows] == [d[0] for d in documents]
    assert repository.counts()["signed_documents"] == 3


def test_duplicate_names_are_made_unique(repository, tmp_path):
    documents = [("a.txt", b"1"), ("a.txt", b"2"), ("sub/a.txt", b"3")]
    result = sign_documents(
        documents, "ACO", AI_KWARGS, "RSA", 1024, repository, str(tmp_path / "packages")
    )
    archive = zipfile.ZipFile(result["package_path"])
    names = [n for n in archive.namelist() if n.endswith(PACKAGE_SUFFIX)]
    assert len(set(names)) == 3


def test_check_signature_detects_modified_document(repository, tmp_path):
    documents, result = signed_batch(repository, tmp_path, count=1)
    package = read_package(open(result["package_path"], "rb").read())
    assert check_signature(package, documents[0][1]) is True
    assert check_signature(package, documents[0][1][:-1]) is False


def test_build_package_roundtrip():
    package = build_package("x.txt", b"isi", b"sig", "RSA", 1024, "pem")
    parsed = read_package(package)
    assert parsed["document"] == b"isi" and parsed["manifest"]["algorithm"] == "RSA"