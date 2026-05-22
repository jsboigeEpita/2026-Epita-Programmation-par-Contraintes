import math
import random
import string

ALPHABET = string.ascii_uppercase


def generate_random_key(length: int) -> list:
    """Return a random permutation of [0..length-1]."""
    key = list(range(length))
    random.shuffle(key)
    return key


def encrypt(text: str, key: list) -> str:
    """
    Columnar transposition encryption.

    key[j] = original column index placed at output segment j.
    Text is uppercased, non-letters removed, then padded with 'X'
    to a multiple of len(key).

    Example (key=[3,1,0,2], plaintext BONJOURPARIS):
      Matrix: B O N J / O U R P / A R I S
      Output: JPS | OUR | BOA | NRI  → JPSOURBOANRI
    """
    text = ''.join(ch for ch in text.upper() if ch in ALPHABET)
    L = len(key)
    n_rows = math.ceil(len(text) / L)
    padded = text + 'X' * (n_rows * L - len(text))
    cols = [''.join(padded[row * L + col] for row in range(n_rows)) for col in range(L)]
    return ''.join(cols[k] for k in key)


def decrypt(text: str, key: list) -> str:
    """
    Columnar transposition decryption.

    key[j] = original column at output segment j.
    Assumes len(text) is divisible by len(key) (i.e., text was padded).
    """
    L = len(key)
    n_rows = len(text) // L
    cols = [''] * L
    for j in range(L):
        cols[key[j]] = text[j * n_rows : (j + 1) * n_rows]
    return ''.join(cols[col][row] for row in range(n_rows) for col in range(L))


def key_accuracy(true_key: list, found_key: list) -> float:
    """Fraction of key positions correctly recovered."""
    if len(true_key) != len(found_key):
        return 0.0
    return sum(1 for a, b in zip(true_key, found_key) if a == b) / len(true_key)
