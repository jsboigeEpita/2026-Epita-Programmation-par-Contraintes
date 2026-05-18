"""
CP-SAT solver for 2x2 Hill cipher.

Two modes
---------
1. Known-plaintext attack  (solve_hill_known_plaintext)
   Given N pairs (plain_block, cipher_block), find K such that K×P ≡ C (mod 26).
   With 2 independent pairs this is usually a unique solution.

2. Ciphertext-only attack  (solve_hill_ciphertext_only)
   Optimise K_inv (the decryption matrix) so that the decoded text scores well
   on bigrams.  Since the ciphertext values are constants, the modular arithmetic
   K_inv[i][j] * c_j is *linear* in K_inv, and add_modulo_equality encodes the
   mod-26 step directly — no auxiliary quotient variables needed.

Model (ciphertext-only)
-----------------------
Variables : kd[i][j] ∈ [0..25]  for i,j ∈ {0,1}  — decryption matrix K_inv
            lin0[b], lin1[b]  ∈ [0..1250]          — linear combination before mod
            p0[b], p1[b]      ∈ [0..25]             — plaintext letters of block b
Constraints :
  lin0[b] = kd[0][0]*c0 + kd[0][1]*c1  (linear, c0/c1 are constants)
  p0[b]   = lin0[b] mod 26              (add_modulo_equality)
  (idem for row 1 → p1[b])
  (optional) gcd(det(K_inv), 26) = 1   — invertibility
Objective  : minimize Σ bigram_cost(p0[b], p1[b])  +  Σ bigram_cost(p1[b], p0[b+1])
"""

import string
from math import gcd
from ortools.sat.python import cp_model

ALPHABET    = string.ascii_uppercase
BIGRAM_SCALE = 1000
MAX_BIGRAM_COST = 20_000
MAX_LINEAR  = 25 * 25 + 25 * 25     # = 1250
COPRIME_26  = [d for d in range(26) if gcd(d, 26) == 1]


def _build_bigram_cost_table(bigram_log_probs: dict) -> list:
    table = []
    for a in ALPHABET:
        for b in ALPHABET:
            import math
            log_p = bigram_log_probs.get(a + b, -20.0)
            cost  = min(MAX_BIGRAM_COST, max(0, round(-log_p * BIGRAM_SCALE)))
            table.append(cost)
    return table


def solve_hill_known_plaintext(
    plain_blocks: list,
    cipher_blocks: list,
    time_limit: float = 15.0,
    verbose: bool = False,
) -> dict:
    """
    Recover the 2x2 Hill encryption key K from known-plaintext pairs.

    Parameters
    ----------
    plain_blocks  : list of (p0, p1) integer tuples (letter indices 0..25)
    cipher_blocks : list of (c0, c1) integer tuples (letter indices 0..25)
    time_limit    : solver budget
    verbose       : CP-SAT verbosity

    Returns
    -------
    dict with 'key' ([[k00,k01],[k10,k11]]), 'status', 'time_s'
    """
    model = cp_model.CpModel()
    K = [[model.new_int_var(0, 25, f'K_{i}_{j}') for j in range(2)] for i in range(2)]

    for idx, ((p0, p1), (c0, c1)) in enumerate(zip(plain_blocks, cipher_blocks)):
        for row, c_val in enumerate([c0, c1]):
            p_vals = [p0, p1]
            # K[row][0]*p0 + K[row][1]*p1 ≡ c_val (mod 26)
            lin = model.new_int_var(0, MAX_LINEAR, f'lin_kp_{idx}_{row}')
            model.add(lin == K[row][0] * p_vals[0] + K[row][1] * p_vals[1])
            c_var = model.new_int_var(c_val, c_val, f'c_kp_{idx}_{row}')
            model.add_modulo_equality(c_var, lin, 26)

    # Invertibility: gcd(det(K), 26) = 1
    _add_invertibility(model, K)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose
    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        found_K = [[solver.value(K[i][j]) for j in range(2)] for i in range(2)]
        return {'key': found_K, 'status': status_name, 'time_s': solver.wall_time}

    return {'key': None, 'status': status_name, 'time_s': solver.wall_time}


def solve_hill_ciphertext_only(
    ciphertext: str,
    bigram_log_probs: dict,
    add_invertibility: bool = True,
    time_limit: float = 30.0,
    verbose: bool = False,
) -> dict:
    """
    Break a 2x2 Hill cipher from ciphertext only using CP-SAT.

    Optimises the decryption matrix K_inv so that decoded bigram score is maximal.
    Uses add_modulo_equality for clean mod-26 encoding (no auxiliary quotient vars).

    Parameters
    ----------
    ciphertext       : encrypted text (even length, letters only)
    bigram_log_probs : dict bigram → log_prob
    add_invertibility: whether to add gcd(det(K_inv), 26) = 1 constraint
    time_limit       : solver budget (seconds)
    verbose          : CP-SAT verbosity

    Returns
    -------
    dict with 'key_inv', 'plaintext', 'status', 'time_s'
    """
    clean = ''.join(ch for ch in ciphertext.upper() if ch in ALPHABET)
    if len(clean) % 2:
        clean += 'A'
    n_blocks = len(clean) // 2
    blocks = [(ord(clean[2*b]) - 65, ord(clean[2*b+1]) - 65) for b in range(n_blocks)]

    cost_table = _build_bigram_cost_table(bigram_log_probs)

    model = cp_model.CpModel()
    kd = [[model.new_int_var(0, 25, f'kd_{i}_{j}') for j in range(2)] for i in range(2)]

    if add_invertibility:
        _add_invertibility(model, kd)

    p0_vars, p1_vars = [], []

    for b, (c0, c1) in enumerate(blocks):
        # Row 0: p0 = (kd[0][0]*c0 + kd[0][1]*c1) mod 26
        lin0 = model.new_int_var(0, MAX_LINEAR, f'lin0_{b}')
        model.add(lin0 == kd[0][0] * c0 + kd[0][1] * c1)
        p0 = model.new_int_var(0, 25, f'p0_{b}')
        model.add_modulo_equality(p0, lin0, 26)

        # Row 1: p1 = (kd[1][0]*c0 + kd[1][1]*c1) mod 26
        lin1 = model.new_int_var(0, MAX_LINEAR, f'lin1_{b}')
        model.add(lin1 == kd[1][0] * c0 + kd[1][1] * c1)
        p1 = model.new_int_var(0, 25, f'p1_{b}')
        model.add_modulo_equality(p1, lin1, 26)

        p0_vars.append(p0)
        p1_vars.append(p1)

    total_cost_terms = []

    # Within-block bigrams: (p0[b], p1[b])
    for b in range(n_blocks):
        scaled  = model.new_int_var(0, 25 * 26, f'sc_wb_{b}')
        model.add(scaled == 26 * p0_vars[b])
        bgidx   = model.new_int_var(0, 675, f'bgidx_wb_{b}')
        model.add(bgidx == scaled + p1_vars[b])
        cost_var = model.new_int_var(0, MAX_BIGRAM_COST, f'cv_wb_{b}')
        model.add_element(bgidx, cost_table, cost_var)
        total_cost_terms.append(cost_var)

    # Between-block bigrams: (p1[b], p0[b+1])
    for b in range(n_blocks - 1):
        scaled  = model.new_int_var(0, 25 * 26, f'sc_bb_{b}')
        model.add(scaled == 26 * p1_vars[b])
        bgidx   = model.new_int_var(0, 675, f'bgidx_bb_{b}')
        model.add(bgidx == scaled + p0_vars[b + 1])
        cost_var = model.new_int_var(0, MAX_BIGRAM_COST, f'cv_bb_{b}')
        model.add_element(bgidx, cost_table, cost_var)
        total_cost_terms.append(cost_var)

    model.minimize(sum(total_cost_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = verbose
    status = solver.solve(model)
    status_name = solver.status_name(status)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        found_kd = [[solver.value(kd[i][j]) for j in range(2)] for i in range(2)]
        plain_chars = []
        for b in range(n_blocks):
            plain_chars.append(ALPHABET[solver.value(p0_vars[b])])
            plain_chars.append(ALPHABET[solver.value(p1_vars[b])])
        return {
            'key_inv':  found_kd,
            'plaintext': ''.join(plain_chars),
            'status':    status_name,
            'time_s':    solver.wall_time,
        }

    return {
        'key_inv':  None, 'plaintext': None,
        'status':   status_name, 'time_s': solver.wall_time,
    }


def _add_invertibility(model: cp_model.CpModel, K: list) -> None:
    """Add gcd(det(K), 26) = 1 constraint to the model."""
    prod1 = model.new_int_var(0, 625, 'det_p1')
    prod2 = model.new_int_var(0, 625, 'det_p2')
    model.add_multiplication_equality(prod1, [K[0][0], K[1][1]])
    model.add_multiplication_equality(prod2, [K[0][1], K[1][0]])
    det_raw = model.new_int_var(-625, 625, 'det_raw')
    model.add(det_raw == prod1 - prod2)
    det_mod = model.new_int_var(0, 25, 'det_mod')
    q_det   = model.new_int_var(-25, 25, 'q_det')
    model.add(det_raw == 26 * q_det + det_mod)
    model.add_allowed_assignments([det_mod], [[d] for d in COPRIME_26])
