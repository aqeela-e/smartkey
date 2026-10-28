import hashlib
import os
import time
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

TAMPER_MODES = ("flip_bit", "append_byte", "truncate")

DOCUMENT_FORMATS = {
    "PDF": ("pdf",),
    "DOCX": ("docx",),
    "TXT": ("txt",),
    "PNG": ("png",),
    "JPG": ("jpg", "jpeg"),
}

MAGIC_BYTES = {
    "PDF": b"%PDF-1.7\n",
    "DOCX": b"PK\x03\x04",
    "TXT": b"",
    "PNG": b"\x89PNG\r\n\x1a\n",
    "JPG": b"\xff\xd8\xff\xe0",
}

Document = Tuple[str, bytes]


def tamper(data: bytes, mode: str) -> bytes:
    if mode == "append_byte":
        return data + b"\x00"
    if mode not in TAMPER_MODES:
        raise ValueError("Mode perubahan tidak dikenal: %s" % mode)
    if not data:
        return b"\x00"
    if mode == "truncate":
        return data[:-1]
    index = int.from_bytes(hashlib.sha256(data).digest()[:8], "big") % len(data)
    altered = bytearray(data)
    altered[index] ^= 0x01
    return bytes(altered)


def format_of(name: str) -> Optional[str]:
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    for label, extensions in DOCUMENT_FORMATS.items():
        if extension in extensions:
            return label
    return None


def group_by_format(
    documents: Iterable[Document], limit_per_format: Optional[int] = None
) -> Dict[str, List[Document]]:
    groups: Dict[str, List[Document]] = {label: [] for label in DOCUMENT_FORMATS}
    for name, data in documents:
        label = format_of(name)
        if label is None:
            continue
        if limit_per_format is None or len(groups[label]) < limit_per_format:
            groups[label].append((name, data))
    return {label: docs for label, docs in groups.items() if docs}


def load_folder(path: str, limit_per_format: Optional[int] = None) -> List[Document]:
    if not os.path.isdir(path):
        raise FileNotFoundError("Folder tidak ditemukan: %s" % path)
    counts = {label: 0 for label in DOCUMENT_FORMATS}
    loaded: List[Document] = []
    for root, _, files in os.walk(path):
        for filename in sorted(files):
            label = format_of(filename)
            if label is None:
                continue
            if limit_per_format is not None and counts[label] >= limit_per_format:
                continue
            with open(os.path.join(root, filename), "rb") as handle:
                loaded.append((os.path.relpath(os.path.join(root, filename), path), handle.read()))
            counts[label] += 1
    return loaded


def synthetic_documents(n_per_format: int, size: int = 2048) -> List[Document]:
    documents: List[Document] = []
    for label, extensions in DOCUMENT_FORMATS.items():
        for i in range(n_per_format):
            body = os.urandom(size)
            if label == "TXT":
                body = body.hex().encode("ascii")
            documents.append(
                ("%s_%05d.%s" % (label.lower(), i, extensions[0]), MAGIC_BYTES[label] + body)
            )
    return documents


def evaluate_document(
    crypto_gen,
    private_key,
    public_key,
    data: bytes,
    modes: Sequence[str] = TAMPER_MODES,
) -> dict:
    start = time.perf_counter()
    signature = crypto_gen.sign(private_key, data)
    sign_ms = (time.perf_counter() - start) * 1000

    start = time.perf_counter()
    original_valid = bool(crypto_gen.verify(public_key, data, signature))
    verify_ms = (time.perf_counter() - start) * 1000

    tampered_valid = {
        mode: bool(crypto_gen.verify(public_key, tamper(data, mode), signature))
        for mode in modes
    }
    return {
        "sign_ms": sign_ms,
        "verify_ms": verify_ms,
        "original_valid": original_valid,
        "tampered_valid": tampered_valid,
        "signature_bytes": len(signature),
    }