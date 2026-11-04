import hashlib
import io
import json
import os
import time
import zipfile
from typing import Callable, List, Optional, Tuple

from modules.crypto.fingerprint import key_fingerprint
from modules.crypto.key_generator import CryptoKeyGenerator

PACKAGE_SUFFIX = ".signed.zip"
MANIFEST_NAME = "manifest.json"
SIGNATURE_NAME = "signature.sig"
PUBLIC_KEY_NAME = "public_key.json"
DOCUMENT_DIR = "document/"
PACKAGE_VERSION = 1

STATUS_VALID = "valid"
STATUS_INVALID = "invalid"
STATUS_UNSIGNED = "unsigned"

REASON_OK = "ok"
REASON_UNSIGNED = "unsigned"
REASON_BAD_PACKAGE = "bad_package"
REASON_MODIFIED = "document_modified"
REASON_SIGNATURE = "signature_invalid"
REASON_MANIFEST = "manifest_mismatch"

REQUIRED_MANIFEST_KEYS = ("document_name", "sha256", "algorithm", "key_size")


class PackageError(Exception):
    pass


class NotAPackage(PackageError):
    pass


def safe_name(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    return base or "dokumen"


def build_package(
    name: str,
    data: bytes,
    signature: bytes,
    algorithm: str,
    key_size: int,
    public_key_export,
    ai: Optional[str] = None,
) -> bytes:
    filename = safe_name(name)
    manifest = {
        "version": PACKAGE_VERSION,
        "document_name": filename,
        "sha256": hashlib.sha256(data).hexdigest(),
        "algorithm": algorithm.upper(),
        "key_size": int(key_size),
        "key_fingerprint": key_fingerprint(public_key_export),
        "ai": ai,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
        archive.writestr(SIGNATURE_NAME, signature)
        archive.writestr(PUBLIC_KEY_NAME, json.dumps(public_key_export))
        archive.writestr(DOCUMENT_DIR + filename, data)
    return buffer.getvalue()


def read_package(data: bytes) -> dict:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise NotAPackage("Bukan arsip ZIP")
    if MANIFEST_NAME not in archive.namelist():
        raise NotAPackage("Manifest tidak ditemukan")
    try:
        manifest = json.loads(archive.read(MANIFEST_NAME))
        if not all(key in manifest for key in REQUIRED_MANIFEST_KEYS):
            raise PackageError("Manifest tidak lengkap")
        return {
            "manifest": manifest,
            "signature": archive.read(SIGNATURE_NAME),
            "public_key": json.loads(archive.read(PUBLIC_KEY_NAME)),
            "document": archive.read(DOCUMENT_DIR + manifest["document_name"]),
        }
    except (KeyError, ValueError, TypeError, zipfile.BadZipFile):
        raise PackageError("Paket rusak")


def check_signature(package: dict, document: bytes) -> bool:
    manifest = package["manifest"]
    try:
        crypto_gen = CryptoKeyGenerator(manifest["algorithm"])
        public_key = crypto_gen.import_public_key(package["public_key"])
        return bool(crypto_gen.verify(public_key, document, package["signature"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def verify_package(
    data: bytes, lookup_key: Optional[Callable[[str], Optional[dict]]] = None
) -> dict:
    result = {
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
    try:
        package = read_package(data)
    except NotAPackage:
        result["status"] = STATUS_UNSIGNED
        result["reason"] = REASON_UNSIGNED
        return result
    except PackageError:
        return result

    manifest = package["manifest"]
    document = package["document"]
    result["document_name"] = manifest["document_name"]
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
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return [(name, data)]
    names = archive.namelist()
    if MANIFEST_NAME in names:
        return [(name, data)]
    inner = [n for n in names if n.endswith(PACKAGE_SUFFIX)]
    if not inner:
        return [(name, data)]
    return [(n, archive.read(n)) for n in inner]