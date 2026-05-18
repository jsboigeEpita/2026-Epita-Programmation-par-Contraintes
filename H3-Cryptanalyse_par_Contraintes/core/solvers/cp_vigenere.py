"""
CP-SAT solver for Vigenère cipher with known key length.

Model
-----
Variables  : key[j]  for j in 0..L-1,  domain [0..25]
             key[j] = v  ↔  shift value at key position j

Objective  : minimize total bigram cost over all consecutive letter pairs.

Key insight: for consecutive positions (i, i+1) with key-position pair (j1, j2):
  plain[i]   = (cipher[i]   - key[j1] + 26) % 26
  plain[i+1] = (cipher[i+1] - key[j2] + 26) % 26
  cost = bigram_cost_table[plain[i]*26 + plain[i+1]]

We precompute an aggregated cost table for each (j1, j2) pair:
  agg_cost[j1][j2][a*26+b] = Σ bigram_cost_table[((ci-a+26)%26)*26 + ((ci1-b+26)%26)]
where the sum runs over all text positions i where (i%L, (i+1)%L) = (j1, j2).

This yields L² element constraints — very efficient for small key lengths (L ≤ 20).
"""

import string
from collections import defaultdict


def _reduce_period(key_arr: list) -> list:
    """Return the smallest repeating unit of key_arr (e.g. [2,4,2,4] → [2,4])."""
    n = len(key_arr)
    for p in range(1, n + 1):
        if n % p == 0 and all(key_arr[i] == key_arr[i % p] for i in range(n)):
            return key_arr[:p]
    return key_arr

from ortools.sat.python import cp_model

ALPHABET = string.ascii_uppercase
BIGRAM_SCALE = 1000
MAX_BIGRAM_COST = 20_000


def _build_bigram_cost_table(bigram_log_probs: dict) -> list:
    table = []
    for a in ALPHABET:
        for b in ALPHABET:
            import math
            log_p = bigram_log_probs.get(a + b, -20.0)
            cost = min(MAX_BIGRAM_COST, max(0, round(-log_p * BIGRAM_SCALE)))
            table.append(cost)
    return table


def solve_vigenere(
    ciphertext: str,
    key_length: int,
    bigram_log_probs: dict,
    time_limit: float = 30.0,
    verbose: bool = False,
) -> dict:
    """
    Break a Vigenère cipher with known key length using CP-SAT.

    Parameters
    ----------
    ciphertext      : encrypted text
    key_length      : known or estimated key length L
    bigram_log_probs: dict bigram → log_prob
    time_limit      : solver time budget (seconds)
    verbose         : print solver progress

    Returns
    -------
    dict with: 'key' (list[int]), 'key_str', 'plaintext', 'status', 'time_s'
    """
    clean = [ord(ch) - ord('A') for ch in ciphertext.upper() if ch in ALPHABET]
    n = len(clean)
    L = key_length
    cost_table = _build_bigram_cost_table(bigram_log_probs)

    # Aggregate bigram cost for each (j1, j2) key-position pair
    # agg[j1][j2][a*26+b] = total cost when key[j1]=a and key[j2]=b
    agg = defaultdict(lambda: defaultdict(lambda: [0] * 676))

    for i in range(n - 1):
        j1, j2 = i % L, (i + 1) % L
        ci, ci1 = clean[i], clean[i + 1]
        for a in range(26):
            for b in range(26):
                plain_i  = (ci  - a + 26) % 26
                plain_i1 = (ci1 - b + 26) % 26
                agg[j1][j2][a * 26 + b] += cost_table[plain_i * 26 + plain_i1]

    model = cp_model.CpModel()
    key = [model.new_int_var(0, 25, f'key_{j}') for j in range(L)]

    total_cost_terms = []

    for j1 in range(L):
        for j2 in range(L):
            if j1 not in agg or j2 not in agg[j1]:
                continue
            agg_table = agg[j1][j2]
            max_val = max(agg_table)
            if max_val == 0:
                continue

            scaled = model.new_int_var(0, 25 * 26, f'sc_{j1}_{j2}')
            model.add(scaled == 26 * key[j1])
            idx = model.new_int_var(0, 675, f'bi_{j1}_{j2}')
            model.add(idx == scaled + key[j2])
            cost_var = model.new_int_var(0, max_val, f'cv_{j1}_{j2}')
            model.add_element(idx, agg_table, cost_var)
            total_cost_terms.append(cost_var)

    model.minimize(sum(total_cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose

    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        found_key_raw = [solver.value(key[j]) for j in range(L)]
        # Reduce periodic keys: CLEFCLEF → CLEF
        found_key = _reduce_period(found_key_raw)
        found_key_str = ''.join(ALPHABET[k] for k in found_key)

        result_chars = []
        key_pos = 0
        for ch in ciphertext.upper():
            if ch in ALPHABET:
                plain_ch = ALPHABET[(ord(ch) - ord('A') - found_key[key_pos % len(found_key)] + 26) % 26]
                result_chars.append(plain_ch)
                key_pos += 1
            else:
                result_chars.append(ch)
        plaintext = ''.join(result_chars)

        return {
            'key': found_key,
            'key_str': found_key_str,
            'plaintext': plaintext,
            'status': status_name,
            'time_s': solver.wall_time,
        }

    return {
        'key': None, 'key_str': None, 'plaintext': None,
        'status': status_name, 'time_s': solver.wall_time,
    }
