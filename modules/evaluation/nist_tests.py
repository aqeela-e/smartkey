import math
from typing import List, Tuple, Dict, Any

from scipy.special import erfc, gammaincc


def bytes_to_bits(data: bytes) -> List[int]:
    """Convert bytes to a list of bits (0s and 1s)."""
    bits = []

    for byte in data:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)

    return bits


def frequency_test(bits: List[int]) -> Tuple[float, bool]:
    """
    NIST Frequency (Monobit) Test.
    Focuses on the proportion of zeroes and ones for the entire sequence.
    Returns (p_value, pass/fail).
    """
    n = len(bits)

    if n == 0:
        return 0.0, False

    s_obs = sum(1 if b == 1 else -1 for b in bits)
    s_obs = abs(s_obs) / math.sqrt(n)

    p_value = erfc(s_obs / math.sqrt(2))

    return float(p_value), bool(p_value >= 0.01)


def block_frequency_test(
    bits: List[int],
    m: int = 8,
) -> Tuple[float, bool]:
    """
    NIST Block Frequency Test.
    Determines whether the frequency of ones in an M-bit block
    is approximately M/2.
    """
    n = len(bits)

    if m <= 0:
        return 0.0, False

    N = n // m

    if N == 0:
        return 0.0, False

    blocks = [bits[i * m:(i + 1) * m] for i in range(N)]
    chi_sq = 0.0

    for block in blocks:
        pi = sum(block) / m
        chi_sq += (pi - 0.5) ** 2

    chi_sq *= 4 * m

    p_value = gammaincc(N / 2, chi_sq / 2)

    return float(p_value), bool(p_value >= 0.01)


def runs_test(bits: List[int]) -> Tuple[float, bool]:
    """
    NIST Runs Test.
    Tests the total number of runs in the sequence.
    """
    n = len(bits)

    if n == 0:
        return 0.0, False

    pi = sum(bits) / n

    # Prerequisite frequency check
    if abs(pi - 0.5) >= (2 / math.sqrt(n)):
        return 0.0, False

    runs = 1

    for i in range(1, n):
        if bits[i] != bits[i - 1]:
            runs += 1

    num = abs(runs - (2 * n * pi * (1 - pi)))
    den = 2 * math.sqrt(2 * n) * pi * (1 - pi)

    if den == 0:
        return 0.0, False

    p_value = erfc(num / den)

    return float(p_value), bool(p_value >= 0.01)


def run_all_tests(data: bytes) -> Dict[str, Dict[str, Any]]:
    """Run all supported NIST tests on the given bytes."""
    bits = bytes_to_bits(data)
    results = {}

    p_val, passed = frequency_test(bits)
    results["Frequency Test"] = {
        "p_value": p_val,
        "passed": passed,
    }

    p_val, passed = block_frequency_test(bits)
    results["Block Frequency Test"] = {
        "p_value": p_val,
        "passed": passed,
    }

    p_val, passed = runs_test(bits)
    results["Runs Test"] = {
        "p_value": p_val,
        "passed": passed,
    }

    return results
