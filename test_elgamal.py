
from Crypto.PublicKey import ElGamal
from Crypto import Random

print("Memulai pengujian ElGamal...")

key = ElGamal.generate(2048, Random.get_random_bytes)

print("Key size:", key.p.bit_length())
print("Private key:", key.has_private())
print("Public key:", key.publickey().y is not None)
print("Pengujian selesai.")
