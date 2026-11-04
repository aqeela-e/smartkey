import csv
import hashlib
import io
import os
import time
import zipfile
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from modules.crypto.key_generator import CryptoKeyGenerator
from modules.evaluation.document_test import format_of
from modules.evaluation.metrics import Evaluator
from modules.experiment.runner import build_ai
from modules.signing.package import PACKAGE_SUFFIX, build_package, safe_name

INDEX_NAME = "index.csv"
INDEX_COLUMNS = ("name", "format", "size_bytes", "sha256", "signature_hex")


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


def _index_csv(rows: List[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(INDEX_COLUMNS)
    for row in rows:
        writer.writerow([row[column] for column in INDEX_COLUMNS])
    return buffer.getvalue()


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
        ("%d_%s%s" % (stamp, names[0], PACKAGE_SUFFIX)) if single else "batch_%d.zip" % stamp,
    )

    rows: List[dict] = []
    sign_times: List[float] = []
    outer = None if single else zipfile.ZipFile(path, "w", zipfile.ZIP_STORED)
    try:
        for index, ((_, data), name) in enumerate(zip(documents, names)):
            begin = time.perf_counter()
            signature = crypto_gen.sign(private_key, data)
            sign_times.append((time.perf_counter() - begin) * 1000)
            package = build_package(
                name, data, signature, crypto_gen.algorithm, key_size, export, ai_name
            )
            if single:
                with open(path, "wb") as handle:
                    handle.write(package)
            else:
                outer.writestr(name + PACKAGE_SUFFIX, package)
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
        if outer is not None:
            outer.writestr(INDEX_NAME, _index_csv(rows))
    finally:
        if outer is not None:
            outer.close()

    first_document = documents[0][1]
    first_signature = bytes.fromhex(rows[0]["signature_hex"])
    begin = time.perf_counter()
    crypto_gen.verify(public_key, first_document, first_signature)
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
                package = build_package(
                    name,
                    data,
                    signature,
                    algorithm,
                    info["key_size"],
                    info["public_key"],
                    result["config"]["ai"],
                )
                outer.writestr("%s/%s%s" % (algorithm, name, PACKAGE_SUFFIX), package)
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