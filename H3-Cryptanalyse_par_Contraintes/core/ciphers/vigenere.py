import string

ALPHABET = string.ascii_uppercase


def str_to_key(key_str: str) -> list:
    """Convert a key string to a list of integers (0..25)."""
    return [ord(ch.upper()) - ord('A') for ch in key_str if ch.upper() in ALPHABET]


def key_to_str(key_arr: list) -> str:
    """Convert a key array to a string."""
    return ''.join(ALPHABET[k] for k in key_arr)


def encrypt(text: str, key) -> str:
    """
    Encrypt text with Vigenère.
    key: str (e.g. 'KEY') or list of ints (e.g. [10, 4, 24])
    Non-letter characters are kept unchanged.
    """
    if isinstance(key, str):
        key = str_to_key(key)
    L = len(key)
    result = []
    j = 0
    for ch in text.upper():
        if ch in ALPHABET:
            result.append(ALPHABET[(ord(ch) - ord('A') + key[j % L]) % 26])
            j += 1
        else:
            result.append(ch)
    return ''.join(result)


def decrypt(text: str, key) -> str:
    """Decrypt text with Vigenère."""
    if isinstance(key, str):
        key = str_to_key(key)
    inv_key = [(-k) % 26 for k in key]
    return encrypt(text, inv_key)
