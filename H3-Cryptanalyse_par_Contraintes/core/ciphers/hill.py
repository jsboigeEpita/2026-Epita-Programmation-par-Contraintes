import random
import string
from math import gcd

ALPHABET = string.ascii_uppercase
COPRIME_26 = {d for d in range(26) if gcd(d, 26) == 1}


def _mod_inv(a: int, m: int = 26) -> int:
    """Modular inverse of a mod m (extended Euclidean)."""
    a = a % m
    for x in range(1, m):
        if (a * x) % m == 1:
            return x
    raise ValueError(f"No modular inverse for {a} mod {m}")


def _matrix_inv_mod26(K: list) -> list:
    """
    Invert a 2x2 matrix mod 26.
    K: [[a, b], [c, d]] as lists of ints.
    Raises ValueError if det is not coprime with 26.
    """
    a, b, c, d = K[0][0], K[0][1], K[1][0], K[1][1]
    det = (a * d - b * c) % 26
    det_inv = _mod_inv(det)
    return [
        [(det_inv * d % 26),        (det_inv * (-b) % 26 + 26) % 26],
        [(det_inv * (-c) % 26 + 26) % 26, (det_inv * a % 26)],
    ]


def generate_random_key() -> list:
    """Return a random invertible 2x2 matrix mod 26."""
    while True:
        K = [[random.randint(0, 25) for _ in range(2)] for _ in range(2)]
        det = (K[0][0] * K[1][1] - K[0][1] * K[1][0]) % 26
        if det in COPRIME_26:
            return K


def encrypt(text: str, key: list) -> str:
    """
    2x2 Hill cipher encryption.
    text is uppercased, non-letters removed, padded with 'X' if odd length.
    key: [[k00,k01],[k10,k11]] — 2x2 integer matrix mod 26.
    """
    text = ''.join(ch for ch in text.upper() if ch in ALPHABET)
    if len(text) % 2:
        text += 'X'
    result = []
    for i in range(0, len(text), 2):
        p0 = ord(text[i])   - 65
        p1 = ord(text[i+1]) - 65
        result.append(ALPHABET[(key[0][0]*p0 + key[0][1]*p1) % 26])
        result.append(ALPHABET[(key[1][0]*p0 + key[1][1]*p1) % 26])
    return ''.join(result)


def decrypt(text: str, key: list) -> str:
    """2x2 Hill cipher decryption via the inverse key matrix."""
    return encrypt(text, _matrix_inv_mod26(key))


def key_accuracy(true_key: list, found_key: list) -> float:
    """Fraction of key matrix entries correctly recovered (0..1)."""
    correct = sum(
        1 for i in range(2) for j in range(2)
        if true_key[i][j] == found_key[i][j]
    )
    return correct / 4


def known_plaintext_attack(plain_pairs: list, cipher_pairs: list) -> list:
    """
    Recover the 2x2 Hill encryption key from two known-plaintext pairs.

    plain_pairs : list of 2 two-letter strings, e.g. ['HE', 'LL']
    cipher_pairs: list of 2 two-letter strings, e.g. ['ZG', 'YK']

    Uses K = C × P^-1 (mod 26) where P, C are 2x2 matrices whose columns
    are the plaintext / ciphertext pairs.

    Raises ValueError if P is not invertible mod 26 (try different pairs).
    """
    P = [
        [ord(plain_pairs[0][0]) - 65, ord(plain_pairs[1][0]) - 65],
        [ord(plain_pairs[0][1]) - 65, ord(plain_pairs[1][1]) - 65],
    ]
    C = [
        [ord(cipher_pairs[0][0]) - 65, ord(cipher_pairs[1][0]) - 65],
        [ord(cipher_pairs[0][1]) - 65, ord(cipher_pairs[1][1]) - 65],
    ]
    P_inv = _matrix_inv_mod26(P)
    return [
        [(C[i][0]*P_inv[0][j] + C[i][1]*P_inv[1][j]) % 26 for j in range(2)]
        for i in range(2)
    ]
