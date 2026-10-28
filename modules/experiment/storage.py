import json
import os
import time
from typing import List

import numpy as np


class ResultEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (bytes, bytearray)):
            return bytes(obj).hex()
        if isinstance(obj, (set, tuple)):
            return list(obj)
        return super().default(obj)


def to_json(result: dict) -> str:
    return json.dumps(result, indent=2, cls=ResultEncoder, ensure_ascii=False)


def save_result(result: dict, kind: str, directory: str) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "%s_%d.json" % (kind, time.time_ns()))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(to_json(result))
    return path


def list_results(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(
        (name for name in os.listdir(directory) if name.endswith(".json")),
        reverse=True,
    )


def load_result(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)