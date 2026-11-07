import io
import os
import zipfile

import pytest

from modules.db import Repository
from modules.evaluation.document_test import synthetic_documents
from modules.experiment.runner import build_ai_kwargs
from modules.signing import (
    STATUS_INVALID,
    STATUS_UNSIGNED,
    STATUS_VALID,
    build_signed_file,
    check_signature,
    expand_uploads,
    has_signature,
    read_signed,
    sign_documents,
    verify_package,
)
from modules.signing.package import (
    EMBED_END,
    REASON_BAD_PACKAGE,
    REASON_MODIFIED,
    REASON_OK,
    REASON_UNSIGNED,
)

AI_KWARGS = build_ai_kwargs({"num_ants": 6, "iterations": 5}, 256, 2.0)


@pytest.fixture()
def repository(tmp_path):
    return Repository(str(tmp_path / "test.db"))


def sign(repository, tmp_path, documents, algorithm="RSA", size=1024):
    return sign_documents(
        documents, "ACO", AI_KWARGS, algorithm, size, repository, str(tmp_path / "packages")
    )


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def test_single_document_stays_a_single_file_in_original_format(repository, tmp_path):
    original = b"\x89PNG\r\n\x1a\n" + os.urandom(500)
    result = sign(repository, tmp_path, [("gambar.png", original)])
    assert result["kind"] == "single"
    assert result["package_path"].endswith("_gambar.png")
    assert not zipfile.is_zipfile(result["package_path"])
    signed = read(result["package_path"])
    assert signed != original
    assert signed.startswith(original)
    assert has_signature(signed)


def test_signed_single_file_verifies_and_is_registered(repository, tmp_path):
    result = sign(repository, tmp_path, [("a.txt", b"isi dokumen")])
    outcome = verify_package(read(result["package_path"]), repository.find_key)
    assert outcome["status"] == STATUS_VALID
    assert outcome["reason"] == REASON_OK
    assert outcome["key_registered"] is True


def test_unsigned_file_is_reported_unsigned(repository):
    outcome = verify_package(b"dokumen biasa yang belum ditandatangani", repository.find_key)
    assert outcome["status"] == STATUS_UNSIGNED
    assert outcome["reason"] == REASON_UNSIGNED


def test_modified_document_is_invalid(repository, tmp_path):
    original = b"isi dokumen yang cukup panjang untuk diubah"
    result = sign(repository, tmp_path, [("a.txt", original)])
    signed = bytearray(read(result["package_path"]))
    signed[3] ^= 0x01
    outcome = verify_package(bytes(signed), repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_MODIFIED


def test_corrupted_trailer_is_bad_package(repository, tmp_path):
    result = sign(repository, tmp_path, [("a.txt", b"isi")])
    signed = read(result["package_path"])
    broken = signed[:-20] + b"x" * 12 + EMBED_END
    outcome = verify_package(broken, repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_BAD_PACKAGE


def test_unregistered_key_is_flagged(repository, tmp_path):
    result = sign(repository, tmp_path, [("a.txt", b"isi")])
    other = Repository(str(tmp_path / "other.db"))
    outcome = verify_package(read(result["package_path"]), other.find_key)
    assert outcome["status"] == STATUS_VALID
    assert outcome["key_registered"] is False


@pytest.mark.parametrize("algorithm,size", [("RSA", 1024), ("DSA", 1024), ("ElGamal", 2048)])
def test_batch_is_one_zip_of_signed_files(repository, tmp_path, algorithm, size):
    documents = synthetic_documents(1)[:5]
    result = sign(repository, tmp_path, documents, algorithm, size)
    assert result["kind"] == "batch"
    assert result["package_path"].endswith(".zip")
    archive = zipfile.ZipFile(result["package_path"])
    names = archive.namelist()
    assert sorted(names) == sorted(d[0] for d in documents)
    expanded = expand_uploads("batch.zip", read(result["package_path"]))
    assert len(expanded) == 5
    for _, data in expanded:
        assert verify_package(data, repository.find_key)["status"] == STATUS_VALID


def test_plain_zip_is_treated_as_one_unsigned_file():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", b"biasa")
    expanded = expand_uploads("plain.zip", buffer.getvalue())
    assert len(expanded) == 1
    assert verify_package(expanded[0][1])["status"] == STATUS_UNSIGNED


def test_signed_zip_based_document_is_not_split(repository, tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", b"<xml/>")
    result = sign(repository, tmp_path, [("laporan.docx", buffer.getvalue())])
    signed = read(result["package_path"])
    assert len(expand_uploads("laporan.docx", signed)) == 1
    assert verify_package(signed, repository.find_key)["status"] == STATUS_VALID


def test_batch_records_are_stored_in_database(repository, tmp_path):
    documents = synthetic_documents(1)[:3]
    result = sign(repository, tmp_path, documents)
    batch = repository.get_batch(result["batch_id"])
    assert batch["doc_count"] == 3 and os.path.exists(batch["package_path"])
    rows = repository.list_signed_documents(result["batch_id"])
    assert [r["name"] for r in rows] == [d[0] for d in documents]
    assert repository.counts()["signed_documents"] == 3


def test_duplicate_names_are_made_unique(repository, tmp_path):
    documents = [("a.txt", b"1"), ("a.txt", b"2"), ("sub/a.txt", b"3")]
    result = sign(repository, tmp_path, documents)
    names = zipfile.ZipFile(result["package_path"]).namelist()
    assert len(names) == 3 and len(set(names)) == 3


def test_check_signature_detects_modified_document(repository, tmp_path):
    original = b"dokumen asli"
    result = sign(repository, tmp_path, [("a.txt", original)])
    package = read_signed(read(result["package_path"]))
    assert package["document"] == original
    assert check_signature(package, original) is True
    assert check_signature(package, original[:-1]) is False


def test_build_signed_file_roundtrip():
    signed = build_signed_file(b"isi", b"sig", "RSA", 1024, "pem")
    parsed = read_signed(signed)
    assert parsed["document"] == b"isi" and parsed["signature"] == b"sig"
    assert parsed["manifest"]["algorithm"] == "RSA"