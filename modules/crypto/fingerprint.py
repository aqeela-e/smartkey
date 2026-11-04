import hashlib
import json


def key_fingerprint(export) -> str:
    canonical = json.dumps(export, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()