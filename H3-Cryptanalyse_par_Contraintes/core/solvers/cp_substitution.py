"""
CP-SAT solver for monoalphabetic substitution cipher.

Model
-----
Variables : key[i] for i in 0..25
            key[i] = j  ↔  cipher letter i decrypts to plaintext letter j
Constraint: AllDifferent(key)          — decryption is a bijection
Objective : minimize  Σ bigram_cost + Σ unigram_rank_cost

  bigram_cost  : for each distinct cipher bigram (c1,c2) with count n,
                 add  n × cost_table[key[c1]×26 + key[c2]]
                 where cost_table[a×26+b] = round(-log_prob('AB') × BIGRAM_SCALE)

  unigram_cost : for each cipher letter c with frequency-rank r_c,
                 add  UNIGRAM_SCALE × |r_c − french_rank[key[c]]|
                 This guides the solver toward frequency-consistent mappings.

Hints from frequency analysis are passed to the solver as an initial assignment.
"""

import string
from collections import Counter

from ortools.sat.python import cp_model

ALPHABET = string.ascii_uppercase
BIGRAM_SCALE = 1000
UNIGRAM_SCALE = 200      # weight of rank-deviation per letter
MAX_BIGRAM_COST = 20_000


def _build_cost_table(bigram_log_probs: dict) -> list:
    """
    Flat list of 676 non-negative integers.
    cost_table[a*26+b] ≡ cost of decrypted bigram (a,b).
    Low value = common French bigram, high value = rare/impossible.
    """
    table = []
    for a in ALPHABET:
        for b in ALPHABET:
            log_p = bigram_log_probs.get(a + b, -20.0)
            cost = min(MAX_BIGRAM_COST, max(0, round(-log_p * BIGRAM_SCALE)))
            table.append(cost)
    return table


def solve_substitution(
    ciphertext: str,
    bigram_log_probs: dict,
    letter_freq_ref: dict = None,
    time_limit: float = 30.0,
    verbose: bool = False,
) -> dict:
    """
    Break a monoalphabetic substitution cipher with CP-SAT.

    Parameters
    ----------
    ciphertext       : encrypted text (uppercase letters, spaces ignored)
    bigram_log_probs : dict bigram_str → log_prob from a reference corpus
    letter_freq_ref  : dict letter → frequency in reference language (optional)
                       When provided, adds unigram costs + frequency hints.
    time_limit       : solver time budget in seconds
    verbose          : print CP-SAT search progress

    Returns
    -------
    dict with keys:
      'key'       : plain→cipher dict (recovered key)
      'plaintext' : recovered plaintext
      'status'    : 'OPTIMAL' | 'FEASIBLE' | 'UNKNOWN' | ...
      'objective' : CP-SAT objective value
      'time_s'    : wall-clock solve time
    """
    clean = ''.join(ch for ch in ciphertext.upper() if ch in ALPHABET)
    cipher_idx = [ord(ch) - ord('A') for ch in clean]

    cipher_letter_counts = Counter(cipher_idx)
    cipher_bigram_counts = Counter(
        (cipher_idx[i], cipher_idx[i + 1]) for i in range(len(cipher_idx) - 1)
    )

    cost_table = _build_cost_table(bigram_log_probs)

    model = cp_model.CpModel()
    key = [model.new_int_var(0, 25, f'key_{i}') for i in range(26)]
    model.add_all_different(key)

    total_cost_terms = []

    # ── Bigram costs ────────────────────────────────────────────────────────
    for (c1, c2), count in cipher_bigram_counts.items():
        # bigram_idx = key[c1]*26 + key[c2]  (index into cost_table)
        scaled = model.new_int_var(0, 25 * 26, f'sc_{c1}_{c2}')
        model.add(scaled == 26 * key[c1])
        bgidx = model.new_int_var(0, 675, f'bi_{c1}_{c2}')
        model.add(bgidx == scaled + key[c2])
        cost_var = model.new_int_var(0, MAX_BIGRAM_COST, f'cv_{c1}_{c2}')
        model.add_element(bgidx, cost_table, cost_var)

        if count == 1:
            total_cost_terms.append(cost_var)
        else:
            wcost = model.new_int_var(0, MAX_BIGRAM_COST * count, f'wc_{c1}_{c2}')
            model.add(wcost == count * cost_var)
            total_cost_terms.append(wcost)

    # ── Unigram rank costs + hints (requires letter_freq_ref) ───────────────
    if letter_freq_ref:
        cipher_sorted = sorted(range(26), key=lambda i: -cipher_letter_counts.get(i, 0))
        cipher_rank = {c: r for r, c in enumerate(cipher_sorted)}

        french_sorted = sorted(range(26), key=lambda i: -letter_freq_ref.get(ALPHABET[i], 0.0))
        french_rank = {p: r for r, p in enumerate(french_sorted)}

        for c in range(26):
            r_c = cipher_rank.get(c, 25)
            uni_table = [UNIGRAM_SCALE * abs(r_c - french_rank.get(p, 25)) for p in range(26)]
            max_uni = max(uni_table)
            uni_cost = model.new_int_var(0, max_uni, f'uni_{c}')
            model.add_element(key[c], uni_table, uni_cost)
            total_cost_terms.append(uni_cost)

        # Hint: start from the frequency-analysis mapping
        for rank, c in enumerate(cipher_sorted):
            model.add_hint(key[c], french_sorted[rank])

    model.minimize(sum(total_cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose

    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        key_arr = [solver.value(key[i]) for i in range(26)]
        # Rebuild plain→cipher dict
        recovered_key = {ALPHABET[key_arr[c_idx]]: ALPHABET[c_idx] for c_idx in range(26)}
        inv = {v: k for k, v in recovered_key.items()}
        plaintext_out = ''.join(inv.get(ch, ch) for ch in ciphertext.upper())
        return {
            'key': recovered_key,
            'plaintext': plaintext_out,
            'status': status_name,
            'objective': solver.objective_value,
            'time_s': solver.wall_time,
        }

    return {'key': None, 'plaintext': None, 'status': status_name,
            'objective': None, 'time_s': solver.wall_time}
