from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from typing import List

import pandas as pd

from .domain import Maneuver, OrbitalInstance, Precedence, SafetyConflict
from .orbit_physics import (
    hohmann_delta_v_mps,
    hohmann_time_of_flight_s,
    orbital_period_s,
    radius_from_altitude_km,
    to_dv_units,
    to_time_slots,
)


@dataclass(frozen=True)
class OrbitalProfile:
    regime: str
    profile_name: str
    altitude_from_km: int
    altitude_to_km: int


def _module_name(i: int) -> str:
    if i == 0:
        return "core"
    if i == 1:
        return "propulsion"
    if i == 2:
        return "power_left"
    if i == 3:
        return "power_right"
    if i == 4:
        return "payload"
    if i == 5:
        return "comm"
    return f"module_{i}"


def _sample_profile(rng: random.Random, module_i: int) -> OrbitalProfile:
    if module_i == 0:
        return OrbitalProfile(
            regime="LEO",
            profile_name="LEO_RAISE",
            altitude_from_km=rng.randint(380, 470),
            altitude_to_km=rng.randint(560, 720),
        )
    if module_i == 1:
        return OrbitalProfile(
            regime="GEO",
            profile_name="MEO_TO_GEO",
            altitude_from_km=rng.randint(10_000, 16_000),
            altitude_to_km=35_786,
        )

    draw = rng.random()
    if draw < 0.55:
        base = rng.randint(520, 760)
        delta = rng.randint(-70, 70)
        target = max(420, base + delta)
        return OrbitalProfile(
            regime="LEO",
            profile_name="LEO_PHASING",
            altitude_from_km=base,
            altitude_to_km=target,
        )
    if draw < 0.85:
        return OrbitalProfile(
            regime="LEO",
            profile_name="LEO_RAISE",
            altitude_from_km=rng.randint(350, 520),
            altitude_to_km=rng.randint(560, 900),
        )
    return OrbitalProfile(
        regime="GEO",
        profile_name="MEO_TO_GEO",
        altitude_from_km=rng.randint(11_000, 20_000),
        altitude_to_km=35_786,
    )


def _comm_visibility_envelope(
    rng: random.Random,
    win_open: int,
    win_close: int,
    min_required: int,
    period_slots: int,
    visibility_slots: int,
) -> tuple[int, int]:
    width = win_close - win_open
    if width <= min_required + 1:
        return win_open, win_close

    modeled_span = visibility_slots + max(1, width // max(1, period_slots)) * period_slots
    target_ratio = rng.uniform(0.72, 0.96)
    wide_span = int(round(width * target_ratio))
    comm_width = max(min_required + 2, min(width, max(modeled_span, wide_span)))
    comm_open_lb = win_open
    comm_open_ub = win_close - comm_width
    if comm_open_ub < comm_open_lb:
        return win_open, win_close

    comm_open = rng.randint(comm_open_lb, comm_open_ub)
    comm_close = comm_open + comm_width
    return comm_open, comm_close


def _profile_dynamics(
    rng: random.Random,
    profile: OrbitalProfile,
) -> dict[str, int]:
    r_from = radius_from_altitude_km(profile.altitude_from_km)
    r_to = radius_from_altitude_km(profile.altitude_to_km)
    base_transfer_dv_mps = hohmann_delta_v_mps(r_from, r_to)
    base_transfer_t_s = hohmann_time_of_flight_s(r_from, r_to)
    target_period_s = orbital_period_s(r_to)

    tr_fast_dur = max(3, to_time_slots(base_transfer_t_s * rng.uniform(0.80, 0.92)))
    tr_eco_dur = max(tr_fast_dur + 1, to_time_slots(base_transfer_t_s * rng.uniform(1.05, 1.20)))
    tr_fast_dv = to_dv_units(base_transfer_dv_mps * rng.uniform(1.07, 1.16))
    tr_eco_dv = max(1, min(tr_fast_dv, to_dv_units(base_transfer_dv_mps * rng.uniform(0.90, 1.00))))

    docking_sync_fraction = rng.uniform(0.03, 0.08)
    base_docking_t_s = target_period_s * docking_sync_fraction
    base_docking_dv_mps = max(8.0, base_transfer_dv_mps * rng.uniform(0.05, 0.12))

    dk_fast_dur = max(2, to_time_slots(base_docking_t_s * rng.uniform(0.85, 0.95)))
    dk_eco_dur = max(dk_fast_dur + 1, to_time_slots(base_docking_t_s * rng.uniform(1.08, 1.30)))
    dk_fast_dv = to_dv_units(base_docking_dv_mps * rng.uniform(1.08, 1.18))
    dk_eco_dv = max(1, min(dk_fast_dv, to_dv_units(base_docking_dv_mps * rng.uniform(0.86, 0.96))))

    period_slots = max(1, to_time_slots(target_period_s))
    visibility_slots = 1 if profile.regime == "LEO" else 6

    return {
        "tr_fast_dur": tr_fast_dur,
        "tr_eco_dur": tr_eco_dur,
        "tr_fast_dv": tr_fast_dv,
        "tr_eco_dv": tr_eco_dv,
        "tr_base_dv_mps": int(round(base_transfer_dv_mps)),
        "tr_base_time_s": int(round(base_transfer_t_s)),
        "dk_fast_dur": dk_fast_dur,
        "dk_eco_dur": dk_eco_dur,
        "dk_fast_dv": dk_fast_dv,
        "dk_eco_dv": dk_eco_dv,
        "dk_base_dv_mps": int(round(base_docking_dv_mps)),
        "dk_base_time_s": int(round(base_docking_t_s)),
        "period_slots": period_slots,
        "visibility_slots": visibility_slots,
    }


def generate_instance(
    n_modules: int = 6,
    horizon: int = 360,
    seed: int = 0,
    safety_density: float = 0.10,
) -> OrbitalInstance:
    """
    Build a synthetic but physically grounded C4 instance.

    Orbital values are derived from:
    - circular orbit altitudes (LEO and GEO-oriented profiles),
    - Hohmann transfer delta-v and transfer time,
    - communication availability envelopes linked to orbital periods.
    """
    rng = random.Random(seed)
    maneuvers: List[Maneuver] = []
    precedences: List[Precedence] = []
    safety_conflicts: List[SafetyConflict] = []

    idx = 0
    transfer_idx = {}
    docking_idx = {}
    profile_counts = {"LEO": 0, "GEO": 0}
    profile_names: set[str] = set()

    for module_i in range(n_modules):
        module = _module_name(module_i)
        profile = _sample_profile(rng, module_i)
        dyn = _profile_dynamics(rng, profile)
        lane = rng.randint(0, 4)

        profile_counts[profile.regime] += 1
        profile_names.add(profile.profile_name)

        transfer_width = rng.randint(
            max(dyn["tr_eco_dur"] + 18, 70),
            max(dyn["tr_eco_dur"] + 72, 150),
        )
        tr_open = rng.randint(0, max(0, horizon // 4))
        tr_close = min(horizon - 4, tr_open + transfer_width)
        if tr_close - tr_open <= dyn["tr_eco_dur"] + 1:
            tr_close = min(horizon - 2, tr_open + dyn["tr_eco_dur"] + 8)

        tr_comm_open, tr_comm_close = _comm_visibility_envelope(
            rng=rng,
            win_open=tr_open,
            win_close=tr_close,
            min_required=dyn["tr_eco_dur"],
            period_slots=dyn["period_slots"],
            visibility_slots=dyn["visibility_slots"],
        )

        transfer = Maneuver(
            idx=idx,
            module=module,
            phase="transfer",
            mission_regime=profile.regime,
            lane=lane,
            orbit_from_km=profile.altitude_from_km,
            orbit_to_km=profile.altitude_to_km,
            base_delta_v_mps=dyn["tr_base_dv_mps"],
            base_time_s=dyn["tr_base_time_s"],
            window_open=tr_open,
            window_close=tr_close,
            comm_open=tr_comm_open,
            comm_close=tr_comm_close,
            duration_fast=dyn["tr_fast_dur"],
            duration_eco=dyn["tr_eco_dur"],
            dv_fast=dyn["tr_fast_dv"],
            dv_eco=dyn["tr_eco_dv"],
        )
        transfer_idx[module_i] = idx
        maneuvers.append(transfer)
        idx += 1

        docking_width = rng.randint(
            max(dyn["dk_eco_dur"] + 12, 50),
            max(dyn["dk_eco_dur"] + 60, 120),
        )
        dk_open_lb = max(0, tr_open + dyn["tr_fast_dur"] // 2)
        dk_open_ub = max(dk_open_lb, min(horizon - docking_width - 2, tr_close + 70))
        dk_open = rng.randint(dk_open_lb, dk_open_ub) if dk_open_ub > dk_open_lb else dk_open_lb
        dk_close = min(horizon - 2, dk_open + docking_width)
        if module_i == 0:
            dk_open = min(dk_open, horizon // 2)
            dk_close = max(dk_close, min(horizon - 1, horizon // 2 + 40))
        else:
            dk_open = max(dk_open, horizon // 3)
            dk_close = max(dk_close, horizon - rng.randint(24, 64))
            dk_close = min(dk_close, horizon - 1)
        if dk_close - dk_open <= dyn["dk_eco_dur"] + 1:
            dk_close = min(horizon - 1, dk_open + dyn["dk_eco_dur"] + 6)

        dk_comm_open, dk_comm_close = _comm_visibility_envelope(
            rng=rng,
            win_open=dk_open,
            win_close=dk_close,
            min_required=dyn["dk_eco_dur"],
            period_slots=dyn["period_slots"],
            visibility_slots=dyn["visibility_slots"],
        )

        docking = Maneuver(
            idx=idx,
            module=module,
            phase="docking",
            mission_regime=profile.regime,
            lane=(lane + 1) % 5,
            orbit_from_km=profile.altitude_to_km,
            orbit_to_km=profile.altitude_to_km,
            base_delta_v_mps=dyn["dk_base_dv_mps"],
            base_time_s=dyn["dk_base_time_s"],
            window_open=dk_open,
            window_close=dk_close,
            comm_open=dk_comm_open,
            comm_close=dk_comm_close,
            duration_fast=dyn["dk_fast_dur"],
            duration_eco=dyn["dk_eco_dur"],
            dv_fast=dyn["dk_fast_dv"],
            dv_eco=dyn["dk_eco_dv"],
        )
        docking_idx[module_i] = idx
        maneuvers.append(docking)
        idx += 1

        precedences.append(Precedence(pred=transfer_idx[module_i], succ=docking_idx[module_i], lag=0))

    for module_i in range(1, n_modules):
        precedences.append(Precedence(pred=docking_idx[0], succ=docking_idx[module_i], lag=0))

    if n_modules > 4:
        precedences.append(Precedence(pred=docking_idx[1], succ=docking_idx[4], lag=0))
    if n_modules > 5:
        precedences.append(Precedence(pred=docking_idx[1], succ=docking_idx[5], lag=0))

    all_dockings = list(docking_idx.values())
    for i in range(len(all_dockings)):
        for j in range(i + 1, len(all_dockings)):
            if rng.random() < 0.02:
                precedences.append(Precedence(pred=all_dockings[i], succ=all_dockings[j], lag=rng.randint(0, 4)))

    n = len(maneuvers)
    for i in range(n):
        for j in range(i + 1, n):
            same_module = maneuvers[i].module == maneuvers[j].module
            both_docking = maneuvers[i].phase == "docking" and maneuvers[j].phase == "docking"
            if both_docking and not same_module and rng.random() < safety_density:
                safety_conflicts.append(SafetyConflict(left=i, right=j, separation=rng.randint(2, 7)))

    min_total = sum(min(m.dv_fast, m.dv_eco) for m in maneuvers)
    max_total = sum(max(m.dv_fast, m.dv_eco) for m in maneuvers)
    total_fuel_budget = min_total + int(0.82 * (max_total - min_total))

    max_single = max(max(m.dv_fast, m.dv_eco) for m in maneuvers)
    mean_single = sum(max(m.dv_fast, m.dv_eco) for m in maneuvers) / len(maneuvers)
    concurrent_dv_capacity = int(max_single + 2.2 * mean_single)

    instance = OrbitalInstance(
        name=f"C4-synth-mod{n_modules}-seed{seed}",
        horizon=horizon,
        maneuvers=maneuvers,
        precedences=precedences,
        safety_conflicts=safety_conflicts,
        total_fuel_budget=total_fuel_budget,
        concurrent_dv_capacity=concurrent_dv_capacity,
        metadata={
            "time_slot_seconds": 600,
            "dv_unit_mps": 10,
            "profile_counts": profile_counts,
            "profiles_present": sorted(profile_names),
        },
    )
    ok, msg = instance.validate()
    if not ok:
        raise ValueError(f"Invalid generated instance: {msg}")
    return instance


def maneuvers_dataframe(instance: OrbitalInstance) -> pd.DataFrame:
    rows = []
    for m in instance.maneuvers:
        row = asdict(m)
        row["name"] = m.name
        row["earliest_start"] = m.earliest_start
        row["latest_end"] = m.latest_end
        rows.append(row)
    return pd.DataFrame(rows).sort_values("idx").reset_index(drop=True)
