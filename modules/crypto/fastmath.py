try:
    import gmpy2

    def powmod(base: int, exponent: int, modulus: int) -> int:
        return int(gmpy2.powmod(base, exponent, modulus))

    def invert(value: int, modulus: int) -> int:
        return int(gmpy2.invert(value, modulus))

except ImportError:

    def powmod(base: int, exponent: int, modulus: int) -> int:
        return pow(base, exponent, modulus)

    def invert(value: int, modulus: int) -> int:
        return pow(value, -1, modulus)