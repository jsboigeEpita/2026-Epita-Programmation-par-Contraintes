import random
import string

ALPHABET = string.ascii_uppercase


def generate_random_key() -> dict:
    """Return a random bijection: plaintext letter -> ciphertext letter."""
    shuffled = list(ALPHABET)
    random.shuffle(shuffled)
    return dict(zip(ALPHABET, shuffled))


def encrypt(text: str, key: dict) -> str:
    """Encrypt text using a substitution key dict (plain -> cipher)."""
    result = []
    for ch in text.upper():
        result.append(key.get(ch, ch))
    return ''.join(result)


def decrypt(text: str, key: dict) -> str:
    """Decrypt text using a substitution key dict (plain -> cipher)."""
    inv_key = {v: k for k, v in key.items()}
    return encrypt(text, inv_key)


def key_to_array(key_dict: dict) -> list:
    """Convert key dict to array: array[cipher_idx] = plain_idx."""
    arr = [0] * 26
    for plain, cipher in key_dict.items():
        c_idx = ord(cipher) - ord('A')
        p_idx = ord(plain) - ord('A')
        arr[c_idx] = p_idx
    return arr


def array_to_key(arr: list) -> dict:
    """Convert array (arr[cipher_idx]=plain_idx) back to plain->cipher dict."""
    key = {}
    for c_idx, p_idx in enumerate(arr):
        plain = ALPHABET[p_idx]
        cipher = ALPHABET[c_idx]
        key[plain] = cipher
    return key


def key_accuracy(true_key: dict, found_key: dict) -> float:
    """Fraction of plaintext letters correctly mapped."""
    correct = sum(1 for p in ALPHABET if true_key.get(p) == found_key.get(p))
    return correct / 26
