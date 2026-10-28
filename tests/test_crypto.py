import hashlib

import pytest

from modules.crypto.key_generator import CryptoKeyGenerator
from modules.crypto.prng import derive_seed

SEED = hashlib.sha256(b"smartkey-test-seed").digest()
DOCUMENT = b"This is a secret document"
ALGORITHMS = (("RSA", 1024), ("DSA", 1024), ("ELGAMAL", 2048))


@pytest.fixture(scope="module")
def keypairs():
    pairs = {}
    for name, size in ALGORITHMS:
        gen = CryptoKeyGenerator(name)
        priv, pub = gen.generate_keys(SEED, key_size=size)
        pairs[name] = (gen, priv, pub)
    return pairs


@pytest.mark.parametrize("name", [a for a, _ in ALGORITHMS])
def test_sign_and_verify_original(keypairs, name):
    gen, priv, pub = keypairs[name]
    signature = gen.sign(priv, DOCUMENT)
    assert isinstance(signature, bytes)
    assert gen.verify(pub, DOCUMENT, signature) is True


@pytest.mark.parametrize("name", [a for a, _ in ALGORITHMS])
def test_modified_document_is_rejected(keypairs, name):
    gen, priv, pub = keypairs[name]
    signature = gen.sign(priv, DOCUMENT)
    assert gen.verify(pub, DOCUMENT + b"x", signature) is False
    assert gen.verify(pub, DOCUMENT[:-1], signature) is False


@pytest.mark.parametrize("name", [a for a, _ in ALGORITHMS])
def test_corrupted_signature_is_rejected(keypairs, name):
    gen, priv, pub = keypairs[name]
    signature = bytearray(gen.sign(priv, DOCUMENT))
    signature[len(signature) // 2] ^= 0x01
    assert gen.verify(pub, DOCUMENT, bytes(signature)) is False


@pytest.mark.parametrize("name", [a for a, _ in ALGORITHMS])
def test_wrong_public_key_is_rejected(name):
    gen = CryptoKeyGenerator(name)
    size = dict(ALGORITHMS)[name]
    _, other_pub = gen.generate_keys(hashlib.sha256(b"other-seed").digest(), key_size=size)
    priv, _ = gen.generate_keys(SEED, key_size=size)
    assert gen.verify(other_pub, DOCUMENT, gen.sign(priv, DOCUMENT)) is False


def test_keygen_is_deterministic_for_same_seed():
    gen = CryptoKeyGenerator("RSA")
    first, _ = gen.generate_keys(SEED, key_size=1024)
    second, _ = gen.generate_keys(SEED, key_size=1024)
    assert first.export_key() == second.export_key()


def test_dsa_signature_is_deterministic(keypairs):
    gen, priv, _ = keypairs["DSA"]
    assert gen.sign(priv, DOCUMENT) == gen.sign(priv, DOCUMENT)


def test_seed_derivation_is_separated_per_algorithm_and_size():
    rsa = derive_seed(SEED, "RSA", 2048)
    assert rsa != derive_seed(SEED, "DSA", 2048)
    assert rsa != derive_seed(SEED, "ELGAMAL", 2048)
    assert rsa != derive_seed(SEED, "RSA", 1024)
    assert rsa == derive_seed(SEED, "rsa", 2048)
    assert len(rsa) == 32


def test_signature_is_over_message_not_precomputed_digest(keypairs):
    gen, priv, pub = keypairs["RSA"]
    signature = gen.sign(priv, DOCUMENT)
    assert gen.verify(pub, hashlib.sha256(DOCUMENT).digest(), signature) is False


def test_unsupported_key_size_is_rejected():
    with pytest.raises(ValueError):
        CryptoKeyGenerator("ELGAMAL").generate_keys(SEED, key_size=1024)
    with pytest.raises(ValueError):
        CryptoKeyGenerator("DSA").generate_keys(SEED, key_size=4096)


def test_unknown_algorithm_is_rejected():
    with pytest.raises(ValueError):
        CryptoKeyGenerator("ECDSA")