import math
import threading
import time
from typing import Optional, Tuple

import numpy as np
from sklearn.neural_network import MLPRegressor

from .base import AIKeyGenerator, randomness_penalty
from .entropy_source import EntropySource, get_entropy_source

_MAX_LAG = 8
_BLOCK = 8
_MIN_BITS = 16

_TRAIN_SEED = 20240601

_SURROGATE_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()

def _zscores(X: np.ndarray) -> np.ndarray:
    N, L = X.shape
    Xi = X.astype(np.int32)
    out = [(2 * Xi.sum(1) - L) / math.sqrt(L)]
    for k in range(1, min(_MAX_LAG, L - 1) + 1):
        m = L - k
        agree = (Xi[:, :m] == Xi[:, k:]).sum(1)
        out.append((2 * agree - m) / math.sqrt(m))
    nb = L // _BLOCK
    if nb >= 1:
        pi = Xi[:, : nb * _BLOCK].reshape(N, nb, _BLOCK).mean(2)
        chi = 4.0 * _BLOCK * ((pi - 0.5) ** 2).sum(1)
        out.append((chi - nb) / math.sqrt(2.0 * nb))
    return np.stack(out, axis=1)

def _penalty_from_z(Z: np.ndarray, tol: float) -> np.ndarray:
    return (np.maximum(0.0, np.abs(Z) - tol) ** 2).sum(axis=-1)

def _features(X: np.ndarray) -> np.ndarray:
    s = 2.0 * X - 1.0
    L = s.shape[1]
    parts = [s] + [s[:, :-k] * s[:, k:] for k in range(1, min(_MAX_LAG, L - 1) + 1)]
    return np.concatenate(parts, axis=1)

def _make_training_set(n: int, L: int, rng: np.random.Generator) -> np.ndarray:
    n1, n2 = n // 2, n // 4
    n3 = n - n1 - n2
    A = rng.integers(0, 2, (n1, L))
    p = rng.uniform(0.35, 0.65, (n2, 1))
    B = (rng.random((n2, L)) < p).astype(np.int64)
    q = rng.uniform(0.35, 0.65, (n3,))
    C = np.zeros((n3, L), dtype=np.int64)
    C[:, 0] = rng.integers(0, 2, n3)
    for i in range(1, L):
        stay = rng.random(n3) < q
        C[:, i] = np.where(stay, C[:, i - 1], 1 - C[:, i - 1])
    X = np.vstack([A, B, C])
    rng.shuffle(X)
    return X

def _train_surrogate(L, hidden_layers, n_samples, max_epochs, time_budget_s, seed):
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)

    X_tr = _make_training_set(n_samples, L, rng)
    Z_tr = _zscores(X_tr)
    F_tr = _features(X_tr)
    X_va = rng.integers(0, 2, (1000, L))
    Z_va = _zscores(X_va)
    F_va = _features(X_va)
    var_va = ((Z_va - Z_va.mean(0)) ** 2).sum(0)

    mlp = MLPRegressor(
        hidden_layer_sizes=hidden_layers,
        activation="relu",
        solver="adam",
        batch_size=256,
        learning_rate_init=1e-2,
        alpha=1e-4,
        random_state=seed if seed is None else int(seed) % (2 ** 31),
    )

    best_r2, best_w, no_imp, epochs = -np.inf, None, 0, 0
    for epochs in range(1, max_epochs + 1):
        mlp.partial_fit(F_tr, Z_tr)
        r2 = float(np.mean(1.0 - ((mlp.predict(F_va) - Z_va) ** 2).sum(0) / var_va))
        if r2 > best_r2 + 1e-4:
            best_r2 = r2
            best_w = ([c.copy() for c in mlp.coefs_], [b.copy() for b in mlp.intercepts_])
            no_imp = 0
        else:
            no_imp += 1
        if no_imp >= 8 or (time.perf_counter() - t0) > time_budget_s:
            break

    mlp.coefs_, mlp.intercepts_ = best_w
    return {
        "model": mlp,
        "val_r2": best_r2,
        "epochs": epochs,
        "train_ms": (time.perf_counter() - t0) * 1000,
    }

class NeuralNetworkGenerator(AIKeyGenerator):

    def generate(
        self,
        bit_length: int,
        hidden_layers: tuple = (100, 50),
        noise_std_dev: float = 1.0,
        tolerance_sigma: float = 2.0,
        candidate: Optional[bytes] = None,
        max_refine_steps: int = 64,
        max_attempts: int = 3,
        train_samples: int = 8000,
        train_epochs: int = 60,
        train_time_budget_s: float = 45.0,
        random_state: Optional[int] = None,
        **kwargs
    ) -> Tuple[bytes, dict]:

        if bit_length < 1:
            raise ValueError("bit_length harus >= 1")
        if noise_std_dev < 0:
            raise ValueError("noise_std_dev harus >= 0")

        start_time = time.perf_counter()

        hidden_layers = tuple(int(h) for h in hidden_layers)
        tol = float(tolerance_sigma)
        source = get_entropy_source(random_state)
        train_seed = int(random_state) if random_state is not None else _TRAIN_SEED

        external = candidate is not None
        if external:
            if len(candidate) != (bit_length + 7) // 8:
                raise ValueError(
                    "panjang candidate (%d byte) tidak sesuai bit_length=%d"
                    % (len(candidate), bit_length)
                )
            cand_bits = self._bytes_to_bits(candidate, bit_length)
            max_attempts = 1
        else:
            cand_bits = None

        trained = bit_length >= _MIN_BITS
        info = None
        cached = False
        if trained:
            key = (bit_length, hidden_layers, int(train_samples), int(train_epochs), train_seed)
            with _CACHE_LOCK:
                info = _SURROGATE_CACHE.get(key)
                cached = info is not None
                if info is None:
                    info = _train_surrogate(
                        bit_length, hidden_layers, int(train_samples),
                        int(train_epochs), float(train_time_budget_s), train_seed,
                    )
                    _SURROGATE_CACHE[key] = info

        best = None
        total_steps = 0
        attempts = 0
        for attempts in range(1, max_attempts + 1):
            bits = cand_bits if external else self._random_bits(bit_length, source)
            init_pen = randomness_penalty(bits.tolist(), tolerance_sigma=tol)
            if init_pen > 0 and trained:
                out_bits, pen, steps, trace = self._refine(
                    bits, info["model"], tol, float(noise_std_dev),
                    int(max_refine_steps), source, init_pen,
                )
            else:
                out_bits, pen, steps, trace = bits, init_pen, 0, [float(init_pen)]
            total_steps += steps
            flips = int((out_bits != bits).sum())
            if best is None or pen < best[0]:
                best = (pen, out_bits, flips, steps, init_pen, trace)
            if pen == 0:
                break

        final_pen, out_bits, flips, steps, init_pen, trace = best
        bit_string = "".join("1" if b else "0" for b in out_bits)
        seed_bytes = self.bit_string_to_bytes(bit_string)

        end_time = time.perf_counter()

        metrics = {
            "algorithm": "Artificial Neural Network (ANN)",
            "time_ms": (end_time - start_time) * 1000,
            "hidden_layers": hidden_layers,
            "noise_std_dev": noise_std_dev,
            "tolerance_sigma": tolerance_sigma,
            "candidate_source": "external" if external else "internal",
            "attempts": attempts,
            "initial_penalty": float(init_pen),
            "best_penalty": float(final_pen),
            "converged": bool(final_pen == 0),
            "refined": bool(flips > 0),
            "bit_flips": flips,
            "refine_steps": total_steps,

            "evaluations": attempts + total_steps,
            "surrogate_trained": bool(trained),
            "surrogate_val_r2": (info["val_r2"] if info else None),
            "surrogate_epochs": (info["epochs"] if info else None),
            "surrogate_train_ms": (info["train_ms"] if info else None),
            "surrogate_cached": cached,
            "convergence_penalty": [float(v) for v in trace],
            "entropy_source": source.name,
            "entropy_source_secure": source.secure,
        }

        return seed_bytes, metrics

    @staticmethod
    def _random_bits(bit_length: int, source: EntropySource) -> np.ndarray:
        return source.bits(bit_length)

    @staticmethod
    def _bytes_to_bits(data: bytes, bit_length: int) -> np.ndarray:
        s = bin(int.from_bytes(data, "big"))[2:].zfill(len(data) * 8)[-bit_length:]
        return np.frombuffer(s.encode(), dtype=np.uint8) - ord("0")

    @staticmethod
    def _refine(bits, model, tol, noise_std, max_steps, source, init_pen=None):
        L = len(bits)
        x = bits.astype(np.int8).copy()
        pen = (
            init_pen
            if init_pen is not None
            else randomness_penalty(x.tolist(), tolerance_sigma=tol)
        )
        best_x, best_pen = x.copy(), pen
        trace = [float(pen)]
        flipped = np.zeros(L, dtype=bool)
        idx = np.arange(L)
        steps = 0

        while pen > 0 and steps < max_steps:
            nb = np.tile(x, (L, 1))
            nb[idx, idx] ^= 1
            batch = np.vstack([x[None, :], nb])
            pen_pred = _penalty_from_z(model.predict(_features(batch)), tol)
            gain = pen_pred[0] - pen_pred[1:]
            scale = float(gain.std()) or 1.0
            score = gain + noise_std * scale * source.normal(L)
            score[flipped] = -np.inf
            j = int(np.argmax(score))
            x[j] ^= 1
            flipped[j] = True
            steps += 1
            pen = randomness_penalty(x.tolist(), tolerance_sigma=tol)
            trace.append(float(pen))
            if pen < best_pen:
                best_pen, best_x = pen, x.copy()

        return best_x, best_pen, steps, trace