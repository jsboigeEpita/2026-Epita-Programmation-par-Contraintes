"""
Hill-climbing attack on monoalphabetic substitution cipher.

Algorithm
---------
1. Build an initial key from letter-frequency analysis.
2. Iteratively try all 26×25/2 = 325 swaps of two plaintext letters in the key.
3. Keep any swap that improves the bigram score.
4. Repeat until no improvement is found.
5. Optionally restart with small random perturbations (random restarts).

Complexity per iteration: O(325 × n) where n = text length.
Typical convergence: 5–30 iterations for 200-letter texts.
"""

import random
import string
from collections import Counter

from core.linguistics.frequency_analysis import clean_text, score_text, score_text_ngram, letter_frequencies

ALPHABET = string.ascii_uppercase


def _freq_key_arr(ciphertext: str, ref_letter_freq: dict) -> list:
    """
    Initial key array from frequency analysis.
    key_arr[cipher_idx] = plain_idx
    """
    cipher_freq = letter_frequencies(ciphertext)
    cipher_sorted = sorted(range(26), key=lambda i: -cipher_freq.get(ALPHABET[i], 0))
    ref_sorted    = sorted(range(26), key=lambda i: -ref_letter_freq.get(ALPHABET[i], 0))

    key_arr = [0] * 26
    for rank, c in enumerate(cipher_sorted):
        key_arr[c] = ref_sorted[rank]
    return key_arr


def _decrypt_with_arr(cipher_clean: str, key_arr: list) -> str:
    return ''.join(ALPHABET[key_arr[ord(ch) - ord('A')]] for ch in cipher_clean)


def _arr_to_key_dict(key_arr: list) -> dict:
    """Convert key_arr (cipher_idx → plain_idx) to plain→cipher dict."""
    return {ALPHABET[key_arr[c]]: ALPHABET[c] for c in range(26)}


def hill_climbing_attack(
    ciphertext: str,
    ngram_log_probs: dict,
    ref_letter_freq: dict,
    n_restarts: int = 5,
    max_iter: int = 200,
    seed: int = None,
    ngram_size: int = 2,
) -> dict:
    """
    Break a monoalphabetic substitution cipher with hill climbing.

    Parameters
    ----------
    ciphertext       : ciphertext string (mixed case, spaces allowed)
    ngram_log_probs  : dict ngram → log_prob (from reference corpus or standard table)
    ref_letter_freq  : dict letter → frequency in reference language
    n_restarts       : number of random-restart attempts
    max_iter         : maximum hill-climbing iterations per restart
    seed             : random seed for reproducibility
    ngram_size       : 2 for bigrams, 3 for trigrams (trigrams give better results)

    Returns
    -------
    dict with keys:
      'key'       : plain→cipher dict
      'plaintext' : recovered plaintext
      'score'     : bigram log-likelihood score (higher = better)
      'n_iter'    : total iterations performed
    """
    if seed is not None:
        random.seed(seed)

    cipher_clean = clean_text(ciphertext)
    best_key_arr = None
    best_score = -float('inf')
    total_iter = 0

    for restart in range(n_restarts):
        key_arr = _freq_key_arr(ciphertext, ref_letter_freq)

        # Add random perturbation on restarts > 0
        if restart > 0:
            n_swaps = restart * 3
            for _ in range(n_swaps):
                i, j = random.sample(range(26), 2)
                key_arr[i], key_arr[j] = key_arr[j], key_arr[i]

        plain = _decrypt_with_arr(cipher_clean, key_arr)
        current_score = score_text_ngram(plain, ngram_log_probs, ngram_size)

        improved = True
        n_iter = 0
        while improved and n_iter < max_iter:
            improved = False
            for i in range(26):
                for j in range(i + 1, 26):
                    # Swap the two plain letters in the key
                    key_arr[i], key_arr[j] = key_arr[j], key_arr[i]
                    new_plain = _decrypt_with_arr(cipher_clean, key_arr)
                    new_score = score_text_ngram(new_plain, ngram_log_probs, ngram_size)
                    if new_score > current_score:
                        current_score = new_score
                        plain = new_plain
                        improved = True
                    else:
                        key_arr[i], key_arr[j] = key_arr[j], key_arr[i]
            n_iter += 1
        total_iter += n_iter

        if current_score > best_score:
            best_score = current_score
            best_key_arr = key_arr.copy()

    best_key = _arr_to_key_dict(best_key_arr)
    inv = {v: k for k, v in best_key.items()}
    best_plain = ''.join(inv.get(ch, ch) for ch in ciphertext.upper())

    return {
        'key': best_key,
        'plaintext': best_plain,
        'score': best_score,
        'n_iter': total_iter,
        'ngram_size': ngram_size,
    }
