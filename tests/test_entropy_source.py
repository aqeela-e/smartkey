import ast
import hashlib
import os
import random

import numpy as np
import pytest
from scipy import stats

from modules.ai import (
    GeneticAlgorithmGenerator,
    AntColonyOptimizationGenerator,
    NeuralNetworkGenerator,
)
from modules.ai.entropy_source import (
    SystemEntropySource,
    SeededEntropySource,
    get_entropy_source,
)

AI_DIR = os.path.join(os.path.dirname(__file__), "..", "modules", "ai")


# ---------------------------------------------------------------------------
# Sifat statistik sumber acak itu sendiri
# ---------------------------------------------------------------------------
def test_system_source_is_statistically_sound():
    src = SystemEntropySource()
    assert src.secure and "os.urandom" in src.name

    u = src.uniform(100000)
    assert u.shape == (100000,) and u.min() >= 0.0 and u.max() < 1.0
    assert abs(u.mean() - 0.5) < 0.005
    assert abs(u.var() - 1 / 12) < 0.002

    b = src.bits(100000)
    assert set(np.unique(b)) <= {0, 1} and abs(b.mean() - 0.5) < 0.01

    # randbelow seragam tanpa bias modulo (n=7 tidak membagi 256)
    counts = np.bincount([src.randbelow(7) for _ in range(35000)], minlength=7)
    assert stats.chisquare(counts).pvalue > 1e-4

    z = src.normal(100000)
    assert abs(z.mean()) < 0.02 and abs(z.std() - 1.0) < 0.02
    assert stats.kstest(z, "norm").pvalue > 1e-4        # Box-Muller benar

    assert src.uniform(0).size == 0 and src.bits(0).size == 0
    assert src.normal(5).shape == (5,) and src.normal(1).shape == (1,)
    assert src.randint(3, 3) == 3
    with pytest.raises(ValueError):
        src.randbelow(0)


def test_seeded_source_is_deterministic_and_flagged_insecure():
    a, b = SeededEntropySource(7), SeededEntropySource(7)
    assert np.array_equal(a.bits(64), b.bits(64)) and np.array_equal(a.normal(9), b.normal(9))
    assert not a.secure and "TIDAK AMAN" in a.name
    assert isinstance(get_entropy_source(None), SystemEntropySource)
    assert isinstance(get_entropy_source(5), SeededEntropySource)


# ---------------------------------------------------------------------------
# Provenance: seluruh keacakan HARUS mengalir lewat os.urandom
# ---------------------------------------------------------------------------
def _fake_urandom(seed: bytes):
    state = {"ctr": 0, "calls": 0, "bytes": 0}

    def fake(n):
        state["calls"] += 1
        state["bytes"] += n
        out = b""
        while len(out) < n:
            out += hashlib.sha256(seed + state["ctr"].to_bytes(8, "big")).digest()
            state["ctr"] += 1
        return out[:n]

    fake.state = state
    return fake


def _runners():
    ann = NeuralNetworkGenerator()
    ann.generate(256, hidden_layers=(10,), train_samples=3000)      # latih & cache DI LUAR patch
    return {
        "GA": lambda: GeneticAlgorithmGenerator().generate(
            256, population_size=10, generations=3)[0],
        "ACO": lambda: AntColonyOptimizationGenerator().generate(
            256, num_ants=5, iterations=4, tolerance_sigma=0.5)[0],
        "ANN": lambda: NeuralNetworkGenerator().generate(
            256, hidden_layers=(10,), train_samples=3000, tolerance_sigma=0.5)[0],
    }


@pytest.mark.parametrize("name", ["GA", "ACO", "ANN"])
def test_all_randomness_flows_through_os_urandom(name, monkeypatch):
    run = _runners()[name]

    def under(seed, poison):
        fake = _fake_urandom(seed)
        monkeypatch.setattr(os, "urandom", fake)
        random.seed(poison)                 # meracuni PRNG global: tidak boleh berpengaruh
        np.random.seed(poison)
        out = run()
        monkeypatch.undo()
        return out, fake.state

    out1, st1 = under(b"S1", 1)
    out2, st2 = under(b"S1", 999)           # aliran sama, PRNG global berbeda -> HARUS identik
    out3, _ = under(b"S2", 1)               # aliran berbeda -> HARUS berbeda
    assert out1 == out2, "%s: keluaran bergantung pada sesuatu selain os.urandom" % name
    assert out1 != out3, "%s: keluaran tidak bergantung pada os.urandom" % name
    assert st1["calls"] > 0 and st1["bytes"] >= 32


# ---------------------------------------------------------------------------
# Audit statis: tidak ada PRNG global di jalur keluaran
# ---------------------------------------------------------------------------
def _prng_usages(path, allowed_funcs=()):
    tree = ast.parse(open(path, encoding="utf-8").read())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == "random" for a in node.names):
            bad.append("import random")
        if isinstance(node, ast.ImportFrom) and node.module in ("random", "secrets", "deap"):
            if node.module != "secrets":
                bad.append("from %s import ..." % node.module)

    def visit(node, func):
        for child in ast.iter_child_nodes(node):
            f = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else func
            if isinstance(child, ast.Attribute):
                v = child.value
                is_np_random = (isinstance(v, ast.Attribute) and v.attr == "random"
                                and isinstance(v.value, ast.Name) and v.value.id in ("np", "numpy"))
                is_random_mod = isinstance(v, ast.Name) and v.id == "random"
                if (is_np_random or is_random_mod) and f not in allowed_funcs:
                    bad.append("%s.%s di %s" % ("np.random" if is_np_random else "random", child.attr, f))
            visit(child, f)

    visit(tree, None)
    return bad


def test_no_global_prng_in_output_path():
    assert _prng_usages(os.path.join(AI_DIR, "genetic_algorithm.py")) == []
    assert _prng_usages(os.path.join(AI_DIR, "ant_colony.py")) == []
    # ANN: np.random hanya untuk data sintetis publik pelatihan surrogate
    assert _prng_usages(
        os.path.join(AI_DIR, "neural_network.py"),
        allowed_funcs=("_make_training_set", "_train_surrogate"),
    ) == []


# ---------------------------------------------------------------------------
# Metrik & mode riset
# ---------------------------------------------------------------------------
def test_default_is_secure_and_seeded_mode_is_reproducible_but_flagged():
    for gen, kw in (
        (GeneticAlgorithmGenerator(), dict(population_size=8, generations=2)),
        (AntColonyOptimizationGenerator(), dict(num_ants=3, iterations=2)),
        (NeuralNetworkGenerator(), dict(hidden_layers=(10,), train_samples=3000)),
    ):
        _, m = gen.generate(256, **kw)
        assert m["entropy_source_secure"] is True and "os.urandom" in m["entropy_source"]

        s1, m1 = gen.generate(256, random_state=11, **kw)
        s2, _ = gen.generate(256, random_state=11, **kw)
        s3, _ = gen.generate(256, random_state=12, **kw)
        assert s1 == s2 and s1 != s3
        assert m1["entropy_source_secure"] is False and "TIDAK AMAN" in m1["entropy_source"]