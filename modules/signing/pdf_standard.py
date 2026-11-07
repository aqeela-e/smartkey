import datetime
import io
import logging
import os
import re
from typing import Optional, Tuple

from Crypto.PublicKey import RSA

from modules.crypto.rsa_handler import RSAHandler

from .errors import NotAPackage, PackageError

logging.getLogger("pyhanko").setLevel(logging.CRITICAL)
logging.getLogger("pyhanko_certvalidator").setLevel(logging.CRITICAL)

try:
    from asn1crypto import cms as asn1_cms
    from asn1crypto import core as asn1_core
    from asn1crypto import keys as asn1_keys
    from asn1crypto import x509 as asn1_x509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.x509.oid import NameOID
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign import signers
    from pyhanko.sign.diff_analysis import ModificationLevel
    from pyhanko.sign.validation import validate_pdf_signature
    from pyhanko.sign.validation.status import SignatureCoverageLevel
    from pyhanko_certvalidator import ValidationContext
    from pyhanko_certvalidator.policy_decl import DisallowWeakAlgorithmsPolicy
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    AVAILABLE = True
except ImportError:
    AVAILABLE = False

PDF_HEADER = b"%PDF-"
BYTE_RANGE_MARK = b"/ByteRange"
FIELD_NAME = "SmartKeySignature"
SIGNER_NAME = "SmartKey Signer"
SIGN_REASON = "Ditandatangani dengan SmartKey"
CERTIFICATE_DAYS = 3650
DIGEST = "sha256"
SIGNATURE_ALGORITHMS = ("sha256_rsa", "rsassa_pkcs1v15")
HEX_REGIONS = (re.compile(rb"<[0-9A-F]*>"), re.compile(rb"<[0-9a-f]*>"))
MIN_RSA_BITS = min(RSAHandler.SUPPORTED_KEY_SIZES)


def is_pdf(data: bytes) -> bool:
    return data[: len(PDF_HEADER)] == PDF_HEADER


def is_signed_pdf(data: bytes) -> bool:
    return AVAILABLE and is_pdf(data) and BYTE_RANGE_MARK in data


def create_signer(private_key, common_name: str = SIGNER_NAME):
    pkcs8 = private_key.export_key(format="DER", pkcs=8)
    crypto_key = serialization.load_der_private_key(pkcs8, None)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(crypto_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=CERTIFICATE_DAYS))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(crypto_key, hashes.SHA256())
    )
    asn1_certificate = asn1_x509.Certificate.load(certificate.public_bytes(serialization.Encoding.DER))
    return signers.SimpleSigner(
        asn1_certificate, asn1_keys.PrivateKeyInfo.load(pkcs8), SimpleCertificateStore()
    )


def sign(signer, data: bytes, reason: str = SIGN_REASON) -> Tuple[bytes, bytes]:
    writer = IncrementalPdfFileWriter(io.BytesIO(data))
    metadata = signers.PdfSignatureMetadata(
        field_name="%s_%s" % (FIELD_NAME, os.urandom(3).hex()),
        md_algorithm=DIGEST,
        reason=reason,
        name=SIGNER_NAME,
    )
    buffer = io.BytesIO()
    signers.sign_pdf(writer, metadata, signer=signer, output=buffer)
    signed = buffer.getvalue()
    embedded = PdfFileReader(io.BytesIO(signed)).embedded_signatures[-1]
    content, _ = _split_contents(bytes(embedded.pkcs7_content))
    return signed, content


def _certificate_is_intact(certificate_der: bytes) -> bool:
    try:
        certificate = x509.load_der_x509_certificate(certificate_der)
        if certificate.subject != certificate.issuer:
            return False
        certificate.public_key().verify(
            certificate.signature,
            certificate.tbs_certificate_bytes,
            padding.PKCS1v15(),
            certificate.signature_hash_algorithm,
        )
        return True
    except Exception:
        return False


def _is_canonical_algorithm(identifier) -> bool:
    rebuilt = type(identifier)(
        {"algorithm": identifier["algorithm"].native, "parameters": asn1_core.Null()}
    )
    return identifier.dump() == rebuilt.dump()


def _identifier_matches_certificate(signer_info, certificate) -> bool:
    identifier = signer_info["sid"].chosen
    tbs = certificate["tbs_certificate"]
    return (
        identifier["issuer"].dump() == tbs["issuer"].dump()
        and identifier["serial_number"].dump() == tbs["serial_number"].dump()
    )


def _contents_region_is_clean(data: bytes, byte_range) -> bool:
    region = data[byte_range[1] : byte_range[2]]
    return any(pattern.fullmatch(region) for pattern in HEX_REGIONS)


def _structure_is_expected(content_info) -> bool:
    try:
        signed_data = content_info["content"]
        signer_infos = signed_data["signer_infos"]
        if len(signer_infos) != 1 or len(signed_data["certificates"]) != 1:
            return False
        signer_info = signer_infos[0]
        if not _identifier_matches_certificate(signer_info, signed_data["certificates"][0].chosen):
            return False
        return (
            content_info["content_type"].native == "signed_data"
            and signed_data["version"].native == "v1"
            and [d["algorithm"].native for d in signed_data["digest_algorithms"]] == [DIGEST]
            and all(_is_canonical_algorithm(d) for d in signed_data["digest_algorithms"])
            and signed_data["encap_content_info"]["content_type"].native == "data"
            and signed_data["encap_content_info"]["content"].native is None
            and signer_info["version"].native == "v1"
            and signer_info["digest_algorithm"]["algorithm"].native == DIGEST
            and _is_canonical_algorithm(signer_info["digest_algorithm"])
            and signer_info["signature_algorithm"]["algorithm"].native in SIGNATURE_ALGORITHMS
            and _is_canonical_algorithm(signer_info["signature_algorithm"])
        )
    except (KeyError, ValueError, TypeError):
        return False


def _split_contents(raw: bytes) -> Tuple[bytes, bytes]:
    used = len(asn1_cms.ContentInfo.load(raw).dump())
    return raw[:used], raw[used:]


def _public_key_info(certificate) -> Tuple[Optional[str], str, Optional[int]]:
    der = certificate.public_key.dump()
    try:
        key = RSA.import_key(der)
    except (ValueError, IndexError, TypeError):
        return None, certificate.public_key.algorithm.upper(), None
    return key.export_key().decode("utf-8"), "RSA", key.size_in_bits()


def _validation_context():
    policy = DisallowWeakAlgorithmsPolicy(rsa_key_size_threshold=MIN_RSA_BITS)
    try:
        return ValidationContext(
            trust_roots=[], allow_fetching=False, algorithm_usage_policy=policy
        )
    except TypeError:
        return ValidationContext(trust_roots=[], allow_fetching=False)


def inspect(data: bytes) -> dict:
    if not is_signed_pdf(data):
        raise NotAPackage("Tidak ada tanda tangan PDF standar")
    try:
        signatures = PdfFileReader(io.BytesIO(data)).embedded_signatures
        if not signatures:
            raise NotAPackage("Tidak ada tanda tangan PDF standar")
        status = validate_pdf_signature(
            signatures[-1], signer_validation_context=_validation_context()
        )
        raw_contents = bytes(signatures[-1].pkcs7_content)
        _, padding = _split_contents(raw_contents)
        structure_ok = _structure_is_expected(asn1_cms.ContentInfo.load(raw_contents))
        public_key_pem, algorithm, key_size = _public_key_info(status.signing_cert)
    except NotAPackage:
        raise
    except Exception:
        raise PackageError("Tanda tangan PDF tidak dapat dibaca")
    return {
        "intact": bool(status.intact),
        "valid": bool(status.valid),
        "entire_file": status.coverage == SignatureCoverageLevel.ENTIRE_FILE,
        "unmodified": status.modification_level == ModificationLevel.NONE,
        "clean_contents": not any(padding)
        and _contents_region_is_clean(data, signatures[-1].byte_range),
        "certificate_intact": structure_ok
        and _certificate_is_intact(status.signing_cert.dump()),
        "public_key": public_key_pem or status.signing_cert.public_key.dump().hex(),
        "algorithm": algorithm,
        "key_size": key_size,
    }