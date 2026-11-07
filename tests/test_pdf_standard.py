import io

import pytest

pytest.importorskip("pyhanko")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from modules.db import Repository
from modules.experiment.runner import build_ai_kwargs
from modules.signing import (
    STATUS_INVALID,
    STATUS_UNSIGNED,
    STATUS_VALID,
    expand_uploads,
    has_signature,
    sign_documents,
    tampered_variants,
    verify_package,
)
from modules.signing.package import REASON_MODIFIED, REASON_OK, REASON_UNSIGNED

AI_KWARGS = build_ai_kwargs({"num_ants": 6, "iterations": 5}, 256, 2.0)


def make_pdf():
    figure = plt.figure()
    plt.plot([1, 2, 3])
    buffer = io.BytesIO()
    figure.savefig(buffer, format="pdf")
    plt.close(figure)
    return buffer.getvalue()


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


def test_rsa_pdf_gets_a_standard_signature_and_stays_a_pdf(repository, tmp_path):
    original = make_pdf()
    result = sign(repository, tmp_path, [("laporan.pdf", original)])
    signed = read(result["package_path"])
    assert result["standard_pdf_count"] == 1
    assert signed.startswith(original)
    assert signed != original
    assert not has_signature(signed)
    assert result["package_path"].endswith("_laporan.pdf")


def test_standard_pdf_signature_verifies_and_key_is_registered(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())])
    outcome = verify_package(read(result["package_path"]), repository.find_key)
    assert outcome["status"] == STATUS_VALID
    assert outcome["reason"] == REASON_OK
    assert outcome["algorithm"] == "RSA"
    assert outcome["key_registered"] is True


def test_every_tamper_on_standard_pdf_is_rejected(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())])
    signed = read(result["package_path"])
    flipped, appended, truncated = tampered_variants(signed)
    assert verify_package(flipped, repository.find_key)["status"] != STATUS_VALID
    for variant in (appended, truncated):
        outcome = verify_package(variant, repository.find_key)
        assert outcome["status"] == STATUS_INVALID
        assert outcome["reason"] == REASON_MODIFIED


def test_modification_inside_signature_padding_is_detected(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())])
    signed = bytearray(read(result["package_path"]))
    start = bytes(signed).find(b"/Contents <") + len(b"/Contents <")
    end = bytes(signed).find(b">", start)
    assert signed[end - 2] == ord("0")
    signed[end - 2] = ord("1")
    outcome = verify_package(bytes(signed), repository.find_key)
    assert outcome["status"] == STATUS_INVALID
    assert outcome["reason"] == REASON_MODIFIED


def test_one_bit_flip_never_passes_across_many_positions(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())])
    signed = read(result["package_path"])
    start = signed.find(b"/Contents <") + len(b"/Contents <")
    end = signed.find(b">", start)
    positions = list(range(0, len(signed), 97)) + list(range(start, end, 211))
    for position in positions:
        altered = bytearray(signed)
        altered[position] ^= 0x01
        assert verify_package(bytes(altered), repository.find_key)["status"] != STATUS_VALID


def test_unsigned_pdf_is_reported_unsigned(repository):
    outcome = verify_package(make_pdf(), repository.find_key)
    assert outcome["status"] == STATUS_UNSIGNED
    assert outcome["reason"] == REASON_UNSIGNED


@pytest.mark.parametrize("algorithm,size", [("DSA", 1024), ("ElGamal", 2048)])
def test_non_rsa_pdf_falls_back_to_smartkey_signature(repository, tmp_path, algorithm, size):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())], algorithm, size)
    signed = read(result["package_path"])
    assert result["standard_pdf_count"] == 0
    assert has_signature(signed)
    assert verify_package(signed, repository.find_key)["status"] == STATUS_VALID


def test_invalid_pdf_structure_falls_back_instead_of_failing(repository, tmp_path):
    broken = b"%PDF-1.7\n" + b"\x00\x01\x02" * 100
    result = sign(repository, tmp_path, [("rusak.pdf", broken)])
    signed = read(result["package_path"])
    assert result["standard_pdf_count"] == 0
    assert verify_package(signed, repository.find_key)["status"] == STATUS_VALID


def test_mixed_batch_uses_standard_for_pdf_and_embedded_for_others(repository, tmp_path):
    documents = [("a.pdf", make_pdf()), ("b.pdf", make_pdf()), ("c.txt", b"teks biasa")]
    result = sign(repository, tmp_path, documents)
    assert result["standard_pdf_count"] == 2 and result["pdf_count"] == 2
    expanded = expand_uploads("batch.zip", read(result["package_path"]))
    assert len(expanded) == 3
    for _, data in expanded:
        assert verify_package(data, repository.find_key)["status"] == STATUS_VALID


def test_case_change_in_signer_name_is_detected(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())])
    signed = read(result["package_path"])
    encoded_name = b"536D6172744B6579205369676E6572"
    positions = []
    cursor = signed.find(encoded_name)
    while cursor != -1:
        positions.append(cursor)
        cursor = signed.find(encoded_name, cursor + 1)
    assert len(positions) >= 2
    for position in positions:
        altered = bytearray(signed)
        altered[position + 1] = ord("7")
        assert verify_package(bytes(altered), repository.find_key)["status"] != STATUS_VALID


def test_rsa_1024_signature_is_accepted_when_unmodified(repository, tmp_path):
    result = sign(repository, tmp_path, [("laporan.pdf", make_pdf())], "RSA", 1024)
    outcome = verify_package(read(result["package_path"]), repository.find_key)
    assert outcome["status"] == STATUS_VALID and outcome["key_size"] == 1024