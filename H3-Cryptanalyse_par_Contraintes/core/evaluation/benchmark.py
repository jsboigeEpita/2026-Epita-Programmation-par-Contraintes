"""
Benchmark utilities for comparing cryptanalysis approaches.

Usage
-----
from core.evaluation.benchmark import run_trials, print_table, success_rate

results = run_trials(
    encrypt_fn=encrypt,
    solve_fn=lambda c: solve_substitution(c, blp),
    key_gen_fn=generate_random_key,
    key_accuracy_fn=key_accuracy,
    plain_text=CORPUS[:1000],
    text_lengths=[100, 200, 400],
    n_trials=10,
)
print_table(results)
"""
import time
import random
import string

ALPHABET = string.ascii_uppercase


def run_trials(
    encrypt_fn,
    solve_fn,
    key_gen_fn,
    key_accuracy_fn,
    plain_text: str,
    text_lengths: list,
    n_trials: int,
    seed: int = 42,
    verbose: bool = False,
) -> dict:
    """
    Run n_trials per text length, measuring key recovery accuracy and time.

    Parameters
    ----------
    encrypt_fn      : callable(text, key) → ciphertext
    solve_fn        : callable(ciphertext) → dict with 'key' entry
    key_gen_fn      : callable() → key
    key_accuracy_fn : callable(true_key, found_key) → float in [0, 1]
    plain_text      : source of plaintext samples (will be repeated if needed)
    text_lengths    : list of ints — number of letters per sample
    n_trials        : number of independent trials per length
    seed            : random seed for reproducibility
    verbose         : print progress

    Returns
    -------
    dict: length → {
        'mean_accuracy' : float,
        'mean_time_s'   : float,
        'success_rate'  : float  (fraction with accuracy >= 0.99),
        'trials'        : list of dicts per trial,
    }
    """
    rng = random.Random(seed)
    # Build a long enough clean source
    clean_source = ''.join(ch for ch in plain_text.upper() if ch in ALPHABET)
    max_len = max(text_lengths)
    while len(clean_source) < max_len * 2:
        clean_source *= 2

    results = {}
    for length in text_lengths:
        trials = []
        for trial in range(n_trials):
            # Sample a fresh random slice
            start = rng.randint(0, len(clean_source) - length)
            sample = clean_source[start : start + length]

            key = key_gen_fn()
            cipher = encrypt_fn(sample, key)

            t0 = time.time()
            res = solve_fn(cipher)
            elapsed = time.time() - t0

            found_key = res.get('key') if res else None
            acc = key_accuracy_fn(key, found_key) if found_key is not None else 0.0
            trials.append({
                'accuracy': acc,
                'time_s': elapsed,
                'status': res.get('status', '?') if res else '?',
            })
            if verbose:
                print(f"  n={length:4d} trial={trial:2d}  acc={acc:.0%}  t={elapsed:.2f}s")

        accs  = [t['accuracy'] for t in trials]
        times = [t['time_s']   for t in trials]
        results[length] = {
            'mean_accuracy': sum(accs)  / len(accs),
            'mean_time_s':   sum(times) / len(times),
            'success_rate':  sum(1 for a in accs if a >= 0.99) / len(accs),
            'trials':        trials,
        }
    return results


def print_table(results: dict, label: str = '') -> None:
    """Print a formatted summary table of benchmark results."""
    header = f"{'n':>6} | {'Précision moy.':>15} | {'Succès (≥99%)':>14} | {'Temps moy.':>12}"
    if label:
        print(f"\n=== {label} ===")
    print(header)
    print('-' * len(header))
    for length in sorted(results):
        r = results[length]
        print(f"{length:>6} | {r['mean_accuracy']:>14.1%} | "
              f"{r['success_rate']:>14.0%} | {r['mean_time_s']:>11.2f}s")


def success_rate(results: dict) -> dict:
    """Return {length: success_rate} for quick access."""
    return {l: r['success_rate'] for l, r in results.items()}


def compare_approaches(approaches: dict, text_lengths: list) -> None:
    """
    Print a side-by-side comparison table for multiple approaches.

    approaches: dict of {label: results_dict}
    """
    labels = list(approaches.keys())
    col_w = 20
    header = f"{'n':>6}" + ''.join(f" | {lb[:col_w]:^{col_w}}" for lb in labels)
    print(header)
    print('-' * len(header))
    for length in sorted(text_lengths):
        row = f"{length:>6}"
        for lb in labels:
            r = approaches[lb].get(length)
            if r:
                row += f" | {r['mean_accuracy']:>6.0%} ({r['mean_time_s']:>5.1f}s)"
            else:
                row += f" | {'N/A':^{col_w}}"
        print(row)
