import hashlib
import os
import time
import zipfile
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from modules.crypto.key_generator import CryptoKeyGenerator
from modules.evaluation.document_test import format_of
from modules.evaluation.metrics import Evaluator
from modules.experiment.runner import build_ai
from modules.signing import pdf_standard
from modules.signing.package import build_signed_file, safe_name, verify_package


def unique_names(names: Sequence[str]) -> List[str]:
    seen: Dict[str, int] = {}
    result = []
    for raw in names:
        name = safe_name(raw)
        count = seen.get(name, 0)
        seen[name] = count + 1
        if count == 0:
            result.append(name)
        else:
            stem, dot, extension = name.rpartition(".")
            result.append("%s_%d.%s" % (stem, count, extension) if dot else "%s_%d" % (name, count))
    return result


def sign_documents(
    documents: Sequence[Tuple[str, bytes]],
    ai_name: str,
    ai_kwargs: dict,
    algorithm: str,
    key_size: int,
    repository,
    packages_dir: str,
    progress: Optional[Callable[[float], None]] = None,
) -> dict:
    if not documents:
        raise ValueError("Tidak ada dokumen untuk ditandatangani")

    seed, ai_metrics = build_ai(ai_name).generate(**ai_kwargs)
    evaluation = Evaluator.evaluate_seed(seed, ai_metrics)

    crypto_gen = CryptoKeyGenerator(algorithm)
    start = time.perf_counter()
    private_key, public_key = crypto_gen.generate_keys(seed, key_size)
    keygen_ms = (time.perf_counter() - start) * 1000
    export = crypto_gen.export_public_key(public_key)
    derived_hex = crypto_gen.derive_seed(seed, key_size).hex()
    key_id = repository.register_key(
        export, crypto_gen.algorithm, key_size, seed.hex(), derived_hex, ai_name
    )

    names = unique_names([name for name, _ in documents])
    os.makedirs(packages_dir, exist_ok=True)
    stamp = time.time_ns()
    single = len(documents) == 1
    path = os.path.join(
        packages_dir,
        ("%d_%s" % (stamp, names[0])) if single else "batch_%d.zip" % stamp,
    )

    standard_signer = None
    if crypto_gen.algorithm == "RSA" and pdf_standard.AVAILABLE:
        standard_signer = pdf_standard.create_signer(private_key)

    rows: List[dict] = []
    sign_times: List[float] = []
    standard_count = 0
    pdf_count = 0
    first_signed = b""
    outer = None if single else zipfile.ZipFile(path, "w", zipfile.ZIP_STORED)
    try:
        for index, ((_, data), name) in enumerate(zip(documents, names)):
            begin = time.perf_counter()
            signed = None
            if pdf_standard.is_pdf(data):
                pdf_count += 1
                if standard_signer is not None:
                    try:
                        signed, signature = pdf_standard.sign(standard_signer, data)
                        standard_count += 1
                    except Exception:
                        signed = None
            if signed is None:
                signature = crypto_gen.sign(private_key, data)
                signed = build_signed_file(
                    data, signature, crypto_gen.algorithm, key_size, export, ai_name
                )
            sign_times.append((time.perf_counter() - begin) * 1000)
            if index == 0:
                first_signed = signed
            if single:
                with open(path, "wb") as handle:
                    handle.write(signed)
            else:
                outer.writestr(name, signed)
            rows.append(
                {
                    "name": name,
                    "format": format_of(name) or "",
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "signature_hex": signature.hex(),
                }
            )
            if progress and ((index + 1) % 25 == 0 or index + 1 == len(documents)):
                progress((index + 1) / len(documents))
    finally:
        if outer is not None:
            outer.close()

    begin = time.perf_counter()
    verify_package(first_signed)
    verify_ms = (time.perf_counter() - begin) * 1000

    batch_id = repository.add_batch(
        "single" if single else "batch",
        crypto_gen.algorithm,
        key_size,
        key_id,
        ai_name,
        len(documents),
        path,
    )
    repository.add_signed_documents(batch_id, key_id, rows)

    return {
        "kind": "single" if single else "batch",
        "batch_id": batch_id,
        "key_id": key_id,
        "package_path": path,
        "doc_count": len(documents),
        "ai": ai_name,
        "ai_kwargs": ai_kwargs,
        "algorithm": crypto_gen.algorithm,
        "key_size": key_size,
        "seed_hex": seed.hex(),
        "derived_seed_hex": derived_hex,
        "evaluation": evaluation,
        "keygen_ms": keygen_ms,
        "sign_ms": sum(sign_times) / len(sign_times),
        "verify_ms": verify_ms,
        "public_key_export": export,
        "pdf_count": pdf_count,
        "standard_pdf_count": standard_count,
    }


def package_experiment(
    repository,
    entries: Dict[str, List[Tuple[str, bytes, bytes]]],
    result: dict,
    packages_dir: str,
) -> Tuple[str, int]:
    os.makedirs(packages_dir, exist_ok=True)
    path = os.path.join(packages_dir, "experiment_%d.zip" % time.time_ns())
    first_trial = result["trials"][0]
    total = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as outer:
        for algorithm, items in entries.items():
            info = first_trial["algorithms"][algorithm]
            key_id = repository.register_key(
                info["public_key"],
                algorithm.upper(),
                info["key_size"],
                first_trial["seed_hex"],
                info["derived_seed_hex"],
                result["config"]["ai"],
            )
            names = unique_names([name for name, _, _ in items])
            rows = []
            for (_, data, signature), name in zip(items, names):
                signed = build_signed_file(
                    data,
                    signature,
                    algorithm,
                    info["key_size"],
                    info["public_key"],
                    result["config"]["ai"],
                )
                outer.writestr("%s/%s" % (algorithm, name), signed)
                rows.append(
                    {
                        "name": name,
                        "format": format_of(name) or "",
                        "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "signature_hex": signature.hex(),
                    }
                )
            batch_id = repository.add_batch(
                "experiment", algorithm.upper(), info["key_size"], key_id,
                result["config"]["ai"], len(items), path,
            )
            repository.add_signed_documents(batch_id, key_id, rows)
            total += len(items)
    return path, total