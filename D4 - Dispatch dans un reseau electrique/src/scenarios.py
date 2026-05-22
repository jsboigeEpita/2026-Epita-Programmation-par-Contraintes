"""Renewable generation scenarios for stochastic unit commitment.

Two stochastic processes are exposed:

* `solar_profile(T)` — deterministic bell curve peaking at midday.
* `wind_profile(T)`  — mean profile with autoregressive noise (windier nights).

`sample_scenarios(...)` returns a tensor ``[n_scenarios][T][n_assets]`` giving
per-hour availability (0-1, multiplied by each asset's nameplate capacity at
the call site).
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional


def solar_profile(T: int = 24, peak_hour: int = 13,
                  width: float = 4.5, max_capacity_factor: float = 0.9) -> List[float]:
    """Bell-shaped capacity factor (0 at night, ~max at noon)."""
    out = []
    for t in range(T):
        x = (t + 0.5 - peak_hour) / width
        cf = max_capacity_factor * math.exp(-x * x)
        if t < 6 or t > 20:
            cf = 0.0
        out.append(round(cf, 4))
    return out


def wind_profile(T: int = 24, mean: float = 0.45, night_bonus: float = 0.10) -> List[float]:
    """Wind mean profile (higher at night, slow diurnal cycle)."""
    out = []
    for t in range(T):
        diurnal = mean + night_bonus * math.cos(2 * math.pi * t / 24.0)
        out.append(round(max(0.0, min(1.0, diurnal)), 4))
    return out


def sample_scenarios(
    asset_means: Dict[str, List[float]],
    n_scenarios: int = 5,
    sigma: float = 0.15,
    seed: Optional[int] = 42,
) -> List[Dict[str, List[float]]]:
    """Sample per-asset hourly capacity factors.

    ``asset_means[asset_id]`` is the deterministic mean profile (one value
    per period). We perturb each hour with an autoregressive Gaussian noise
    (AR(1), ρ=0.7) clipped to [0, 1].

    The returned list has one dict per scenario, each mapping
    ``asset_id -> [cf_0, cf_1, …, cf_{T-1}]``.
    """
    rng = random.Random(seed)
    scenarios = []
    rho = 0.7
    for s in range(n_scenarios):
        scen: Dict[str, List[float]] = {}
        for aid, mean in asset_means.items():
            cfs = []
            noise = 0.0
            for t, m in enumerate(mean):
                noise = rho * noise + math.sqrt(1 - rho * rho) * rng.gauss(0, sigma)
                cf = max(0.0, min(1.0, m + noise))
                # solar must remain zero when mean is zero (night)
                if m == 0.0:
                    cf = 0.0
                cfs.append(round(cf, 4))
            scen[aid] = cfs
        scenarios.append(scen)
    return scenarios
