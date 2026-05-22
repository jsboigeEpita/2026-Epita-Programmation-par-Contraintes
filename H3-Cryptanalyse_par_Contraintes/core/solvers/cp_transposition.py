"""
CP-SAT solver for columnar transposition cipher with known key length.

Model
-----
Variables : pos[c] for c in 0..L-1, domain [0..L-1]
            pos[c] = j  ↔  original column c is placed at output segment j
Constraint: AllDifferent(pos)
Objective : minimize total bigram cost of the reconstructed plaintext

Key insight — within-row bigrams:
  plain[row*L + c]     = cipher[ pos[c]   * n_rows + row ]
  plain[row*L + c + 1] = cipher[ pos[c+1] * n_rows + row ]

For each consecutive column pair (c, c+1) and each pair of output positions (p, q):
  agg_table[p*L + q] = Σ_row  bigram_cost( cipher[p*n_rows+row], cipher[q*n_rows+row] )

→ Only L-1 AddElement constraints (one per consecutive column pair), all sharing the
  same aggregate table — very efficient for small key lengths (L ≤ 12).
"""

import string
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


def solve_transposition(
    ciphertext: str,
    key_length: int,
    bigram_log_probs: dict,
    time_limit: float = 30.0,
    verbose: bool = False,
) -> dict:
    """
    Break a columnar transposition cipher with known key length using CP-SAT.

    Parameters
    ----------
    ciphertext       : encrypted text (letters only, length must be divisible by key_length)
    key_length       : known or estimated key length L
    bigram_log_probs : dict bigram → log_prob
    time_limit       : solver time budget (seconds)
    verbose          : print solver progress

    Returns
    -------
    dict with: 'key' (list[int]), 'plaintext', 'status', 'time_s'
    key[j] = original column placed at output segment j (same convention as transposition.encrypt)
    """
    clean = ''.join(ch for ch in ciphertext.upper() if ch in ALPHABET)
    n = len(clean)
    L = key_length

    if n % L != 0:
        raise ValueError(f"Ciphertext length {n} must be divisible by key_length {L}. "
                         f"Pad the plaintext before encrypting.")

    n_rows = n // L
    cost_table = _build_bigram_cost_table(bigram_log_probs)

    # Precompute aggregate bigram cost for all (p, q) segment index pairs:
    # agg_table[p*L + q] = Σ_row bigram_cost(clean[p*n_rows+row], clean[q*n_rows+row])
    agg_table = [0] * (L * L)
    for p in range(L):
        for q in range(L):
            total = 0
            for row in range(n_rows):
                a_idx = ord(clean[p * n_rows + row]) - 65
                b_idx = ord(clean[q * n_rows + row]) - 65
                total += cost_table[a_idx * 26 + b_idx]
            agg_table[p * L + q] = total

    max_agg = max(agg_table) if agg_table else 1

    model = cp_model.CpModel()
    pos = [model.new_int_var(0, L - 1, f'pos_{c}') for c in range(L)]
    model.add_all_different(pos)

    total_cost_terms = []
    for c in range(L - 1):
        pq_idx = model.new_int_var(0, L * L - 1, f'pq_{c}')
        scaled = model.new_int_var(0, (L - 1) * L, f'sc_{c}')
        model.add(scaled == L * pos[c])
        model.add(pq_idx == scaled + pos[c + 1])
        cost_var = model.new_int_var(0, max_agg, f'cv_{c}')
        model.add_element(pq_idx, agg_table, cost_var)
        total_cost_terms.append(cost_var)

    model.minimize(sum(total_cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose

    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        pos_arr = [solver.value(pos[c]) for c in range(L)]

        # pos[c] = j means column c → segment j
        # key[j] = c means segment j came from column c  (encrypt convention)
        key_arr = [0] * L
        for c, j in enumerate(pos_arr):
            key_arr[j] = c

        # Reconstruct plaintext
        cols = [''] * L
        for j in range(L):
            cols[key_arr[j]] = clean[j * n_rows : (j + 1) * n_rows]
        plaintext = ''.join(cols[col][row] for row in range(n_rows) for col in range(L))

        return {
            'key': key_arr,
            'plaintext': plaintext,
            'status': status_name,
            'time_s': solver.wall_time,
        }

    return {'key': None, 'plaintext': None, 'status': status_name, 'time_s': solver.wall_time}
