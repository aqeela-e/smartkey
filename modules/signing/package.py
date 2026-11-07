import base64
import hashlib
import json
import os
import struct
import time
import zipfile
import io
from typing import Callable, List, Optional, Tuple

from modules.crypto.fingerprint import key_fingerprint
from modules.crypto.key_generator import CryptoKeyGenerator
from modules.evaluation.document_test import TAMPER_MODES, tamper

from . import pdf_standard
from .errors import NotAPackage, PackageError

EMBED_START = b"\n--SMARTKEY-SIGNATURE-BEGIN--\n"
EMBED_END = b"SMKYSIG1"
EMBED_VERSION = 1

STATUS_VALID = "valid"
STATUS_INVALID = "invalid"
STATUS_UNSIGNED = "unsigned"

REASON_OK = "ok"
REASON_UNSIGNED = "unsigned"
REASON_BAD_PACKAGE = "bad_package"
REASON_MODIFIED = "document_modified"
REASON_SIGNATURE = "signature_invalid"
REASON_MANIFEST = "manifest_mismatch"
REASON_CERTIFICATE = "certificate_invalid"

REQUIRED_META_KEYS = ("algorithm", "key_size", "sha256", "signature", "public_key")


def safe_name(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    return base or "dokumen"


def has_signature(data: bytes) -> bool:
    return data.endswith(EMBED_END)


def is_signed(data: bytes) -> bool:
    return has_signature(data) or pdf_standard.is_signed_pdf(data)


def build_signed_file(
    data: bytes,
    signature: bytes,
    algorithm: str,
    key_size: int,
    public_key_export,
    ai: Optional[str] = None,
) -> bytes:
    meta = {
        "version": EMBED_VERSION,
        "algorithm": algorithm.upper(),
        "key_size": int(key_size),
        "sha256": hashlib.sha256(data).hexdigest(),
        "key_fingerprint": key_fingerprint(public_key_export),
        "ai": ai,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key": public_key_export,
    }
    payload = json.dumps(meta, separators=(",", ":")).encode("utf-8")
    return data + EMBED_START + payload + struct.pack(">I", len(payload)) + EMBED_END


def read_signed(data: bytes) -> dict:
    if not has_signature(data) or len(data) < len(EMBED_END) + 4:
        raise NotAPackage("Tidak ada tanda tangan")
    try:
        (length,) = struct.unpack(">I", data[-len(EMBED_END) - 4 : -len(EMBED_END)])
        payload_end = len(data) - len(EMBED_END) - 4
        payload_start = payload_end - length
        marker_start = payload_start - len(EMBED_START)
        if marker_start < 0 or data[marker_start:payload_start] != EMBED_START:
            raise PackageError("Penanda tanda tangan rusak")
        meta = json.loads(data[payload_start:payload_end])
        if not all(key in meta for key in REQUIRED_META_KEYS):
            raise PackageError("Data tanda tangan tidak lengkap")
        return {
            "manifest": {key: meta[key] for key in meta if key not in ("signature", "public_key")},
            "signature": base64.b64decode(meta["signature"]),
            "public_key": meta["public_key"],
            "document": data[:marker_start],
        }
    except PackageError:
        raise
    except (ValueError, TypeError, struct.error):
        raise PackageError("Data tanda tangan rusak")


def check_signature(package: dict, document: bytes) -> bool:
    manifest = package["manifest"]
    try:
        crypto_gen = CryptoKeyGenerator(manifest["algorithm"])
        public_key = crypto_gen.import_public_key(package["public_key"])
        return bool(crypto_gen.verify(public_key, document, package["signature"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def _blank_result() -> dict:
    return {
        "status": STATUS_INVALID,
        "reason": REASON_BAD_PACKAGE,
        "document_name": None,
        "algorithm": None,
        "key_size": None,
        "sha256": None,
        "hash_match": None,
        "signature_valid": None,
        "key_registered": None,
        "key_fingerprint": None,
        "key_id": None,
    }


def _verify_standard_pdf(data: bytes, lookup_key, result: dict) -> dict:
    try:
        info = pdf_standard.inspect(data)
    except NotAPackage:
        result["status"] = STATUS_UNSIGNED
        result["reason"] = REASON_UNSIGNED
        return result
    except PackageError:
        return result

    result["algorithm"] = info["algorithm"]
    result["key_size"] = info["key_size"]
    result["sha256"] = hashlib.sha256(data).hexdigest()
    result["hash_match"] = info["intact"]
    result["signature_valid"] = info["valid"]
    result["key_fingerprint"] = key_fingerprint(info["public_key"])

    if lookup_key is not None:
        record = lookup_key(result["key_fingerprint"])
        result["key_registered"] = record is not None
        result["key_id"] = record["id"] if record else None

    unchanged = info["entire_file"] and info["unmodified"] and info["clean_contents"]
    if info["intact"] and info["valid"] and unchanged and info["certificate_intact"]:
        result["status"] = STATUS_VALID
        result["reason"] = REASON_OK
    elif not info["valid"] and info["intact"]:
        result["reason"] = REASON_SIGNATURE
    elif info["intact"] and info["valid"] and unchanged:
        result["reason"] = REASON_CERTIFICATE
    else:
        result["reason"] = REASON_MODIFIED
    return result


def verify_package(
    data: bytes, lookup_key: Optional[Callable[[str], Optional[dict]]] = None
) -> dict:
    result = _blank_result()
    if not has_signature(data) and pdf_standard.is_signed_pdf(data):
        return _verify_standard_pdf(data, lookup_key, result)
    try:
        package = read_signed(data)
    except NotAPackage:
        result["status"] = STATUS_UNSIGNED
        result["reason"] = REASON_UNSIGNED
        return result
    except PackageError:
        return result

    manifest = package["manifest"]
    document = package["document"]
    result["document_name"] = manifest.get("document_name")
    result["algorithm"] = manifest["algorithm"]
    result["key_size"] = manifest["key_size"]
    result["sha256"] = hashlib.sha256(document).hexdigest()
    result["hash_match"] = result["sha256"] == manifest["sha256"]
    result["signature_valid"] = check_signature(package, document)
    result["key_fingerprint"] = key_fingerprint(package["public_key"])

    if lookup_key is not None:
        record = lookup_key(result["key_fingerprint"])
        result["key_registered"] = record is not None
        result["key_id"] = record["id"] if record else None

    if result["signature_valid"] and result["hash_match"]:
        result["status"] = STATUS_VALID
        result["reason"] = REASON_OK
    elif not result["signature_valid"] and not result["hash_match"]:
        result["reason"] = REASON_MODIFIED
    elif not result["signature_valid"]:
        result["reason"] = REASON_SIGNATURE
    else:
        result["reason"] = REASON_MANIFEST
    return result


def expand_uploads(name: str, data: bytes) -> List[Tuple[str, bytes]]:
    if is_signed(data):
        return [(name, data)]
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return [(name, data)]
    members = [n for n in archive.namelist() if not n.endswith("/")]
    if not any(is_signed(archive.read(n)) for n in members):
        return [(name, data)]
    return [(n, archive.read(n)) for n in members]


def tampered_variants(data: bytes) -> List[bytes]:
    if has_signature(data):
        document = read_signed(data)["document"]
        trailer = data[len(document):]
        return [tamper(document, mode) + trailer for mode in TAMPER_MODES]
    return [tamper(data, mode) for mode in TAMPER_MODES]