import math
import string
from collections import Counter

ALPHABET = string.ascii_uppercase
SMOOTHING = 1e-9  # Near-zero smoothing: zero-count ngrams get very negative log-prob


def clean_text(text: str) -> str:
    """Keep only uppercase ASCII letters."""
    return ''.join(ch for ch in text.upper() if ch in ALPHABET)


def letter_frequencies(text: str) -> dict:
    """Return frequency of each letter (0..1) in cleaned text."""
    text = clean_text(text)
    total = len(text)
    if total == 0:
        return {ch: 0.0 for ch in ALPHABET}
    counts = Counter(text)
    return {ch: counts.get(ch, 0) / total for ch in ALPHABET}


def bigram_counts(text: str) -> Counter:
    """Return raw bigram counts from cleaned text."""
    text = clean_text(text)
    return Counter(text[i:i+2] for i in range(len(text) - 1))


def bigram_log_probs(reference_text: str) -> dict:
    """
    Compute log-probabilities for all 26×26 bigrams from a reference corpus.
    Uses Laplace smoothing so every bigram has a non-zero probability.
    Returns dict: bigram_str -> log_prob (e.g. 'ES' -> -2.34)
    """
    counts = bigram_counts(reference_text)
    total = sum(counts.values())
    log_probs = {}
    for a in ALPHABET:
        for b in ALPHABET:
            bg = a + b
            p = (counts.get(bg, 0) + SMOOTHING) / (total + 676 * SMOOTHING)
            log_probs[bg] = math.log(p)
    return log_probs


def trigram_counts(text: str) -> Counter:
    """Return raw trigram counts from cleaned text."""
    text = clean_text(text)
    return Counter(text[i:i+3] for i in range(len(text) - 2))


def trigram_log_probs(reference_text: str) -> dict:
    """
    Compute log-probabilities for all 26³=17576 trigrams from a reference corpus.
    Uses Laplace smoothing.
    """
    counts = trigram_counts(reference_text)
    total = sum(counts.values())
    n_grams = 26 ** 3
    log_probs = {}
    for a in ALPHABET:
        for b in ALPHABET:
            for c in ALPHABET:
                tg = a + b + c
                p = (counts.get(tg, 0) + SMOOTHING) / (total + n_grams * SMOOTHING)
                log_probs[tg] = math.log(p)
    return log_probs


def score_text_ngram(text: str, log_probs: dict, n: int = 2) -> float:
    """Score a text using n-gram log-probabilities (n=2 bigrams, n=3 trigrams)."""
    text = clean_text(text)
    return sum(log_probs.get(text[i:i+n], -20.0) for i in range(len(text) - n + 1))


def score_text(text: str, log_probs: dict) -> float:
    """Compute total log-probability score of a text using bigram model."""
    text = clean_text(text)
    return sum(log_probs.get(text[i:i+2], -20.0) for i in range(len(text) - 1))


def index_of_coincidence(text: str) -> float:
    """
    Compute the Index of Coincidence (IC).
    IC ≈ 0.065 for French, 0.061 for English, 0.038 for random text.
    """
    text = clean_text(text)
    n = len(text)
    if n < 2:
        return 0.0
    counts = Counter(text)
    return sum(f * (f - 1) for f in counts.values()) / (n * (n - 1))


def detect_key_length_ic(ciphertext: str, max_length: int = 20) -> list:
    """
    Estimate Vigenère key length using the Index of Coincidence.
    For the correct length L, each sub-sequence has IC ≈ 0.065 (French).

    Strategy:
    - Compute mean IC for each candidate length
    - Apply a small length penalty to prefer shorter keys (avoid detecting multiples)
    - Return a list of (length, adjusted_score) sorted descending
    """
    text = clean_text(ciphertext)
    scores = []
    for L in range(1, max_length + 1):
        ics = []
        for start in range(L):
            sub = text[start::L]
            if len(sub) > 1:
                ics.append(index_of_coincidence(sub))
        if ics:
            mean_ic = sum(ics) / len(ics)
            # Penalize longer keys: subtract a small amount proportional to L
            # This helps prefer the fundamental period over its multiples
            adjusted = mean_ic - 0.0005 * (L - 1)
            scores.append((L, adjusted))
    return sorted(scores, key=lambda x: -x[1])


def kasiski_test(ciphertext: str, ngram_len: int = 3) -> dict:
    """
    Kasiski test: find repeated n-grams in the ciphertext and their distances.
    The GCD of the distances is likely the key length.
    Returns a dict of {ngram: [distances]}.
    """
    from math import gcd
    from functools import reduce

    text = clean_text(ciphertext)
    positions = {}
    for i in range(len(text) - ngram_len + 1):
        ng = text[i:i + ngram_len]
        positions.setdefault(ng, []).append(i)

    repeated = {ng: ps for ng, ps in positions.items() if len(ps) > 1}
    distances = {}
    for ng, ps in repeated.items():
        dists = [ps[i+1] - ps[i] for i in range(len(ps)-1)]
        distances[ng] = dists

    if distances:
        all_dists = [d for dists in distances.values() for d in dists]
        g = reduce(gcd, all_dists)
        distances['_gcd'] = g

    return distances


def frequency_attack(ciphertext: str, ref_letter_freq: dict) -> dict:
    """
    Classical frequency attack: map the most frequent cipher letters
    to the most frequent plain letters from the reference.
    Returns a plain->cipher key dict.
    """
    cipher_freq = letter_frequencies(ciphertext)
    cipher_sorted = sorted(cipher_freq.items(), key=lambda x: -x[1])
    ref_sorted = sorted(ref_letter_freq.items(), key=lambda x: -x[1])
    # key: plain letter -> cipher letter
    key = {}
    for (cipher_ch, _), (plain_ch, _) in zip(cipher_sorted, ref_sorted):
        key[plain_ch] = cipher_ch
    return key
