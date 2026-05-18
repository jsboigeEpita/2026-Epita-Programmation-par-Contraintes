"""Génère les datasets benchmark (niveau C) dans data/synthetic/.

Tailles produites pour chacune des distributions ``random`` et ``regions`` :
    small  : ~10-16 items, 20-30 bids   (3 seeds)
    med    : ~30-36 items, 100 bids     (3 seeds)
    large  : ~100 items, 500 bids       (3 seeds)
    stress : ~200 items, 1000 bids      (1 seed)

Utilisation :
    python scripts/build_benchmarks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wdp.generator import generate_random_instance, generate_regions_instance


OUT_DIR = ROOT / "data" / "synthetic"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Distribution random -------------------------------------------------
    random_specs = [
        # (label, n_items, n_bids, n_bidders, seeds)
        ("small",  10,  20,  5,  [0, 1, 2]),
        ("med",    30,  100, 10, [0, 1, 2]),
        ("large",  100, 500, 30, [0, 1, 2]),
        ("stress", 200, 1000, 50, [0]),
    ]
    for label, n_items, n_bids, n_bidders, seeds in random_specs:
        for seed in seeds:
            inst = generate_random_instance(
                n_items=n_items,
                n_bids=n_bids,
                n_bidders=n_bidders,
                avg_bundle_size=3.0,
                synergy=0.2,
                max_bids_per_bidder=max(2, n_bids // n_bidders + 5),
                seed=seed,
                name=f"random_{label}_seed{seed}",
            )
            path = OUT_DIR / f"random_{label}_seed{seed}.json"
            inst.to_json(path)
            print(f"  wrote {path.name:35s}  items={inst.n_items}  bids={inst.n_bids}  xor_groups={len(inst.xor_groups)}")

    # --- Distribution regions ------------------------------------------------
    regions_specs = [
        # (label, grid_h, grid_w, n_bids, n_bidders, seeds)
        ("small",  4,  4,  30,   5,  [0, 1, 2]),
        ("med",    6,  6,  100,  10, [0, 1, 2]),
        ("large",  10, 10, 500,  30, [0, 1, 2]),
        ("stress", 14, 14, 1000, 50, [0]),
    ]
    for label, h, w, n_bids, n_bidders, seeds in regions_specs:
        for seed in seeds:
            inst = generate_regions_instance(
                grid_height=h,
                grid_width=w,
                n_bids=n_bids,
                n_bidders=n_bidders,
                max_rect_size=3,
                synergy=0.3,
                max_bids_per_bidder=max(2, n_bids // n_bidders + 5),
                seed=seed,
                name=f"regions_{label}_seed{seed}",
            )
            path = OUT_DIR / f"regions_{label}_seed{seed}.json"
            inst.to_json(path)
            print(f"  wrote {path.name:35s}  items={inst.n_items}  bids={inst.n_bids}  xor_groups={len(inst.xor_groups)}")


if __name__ == "__main__":
    main()
