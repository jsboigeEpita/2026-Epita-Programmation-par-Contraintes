from __future__ import annotations

import math

# Standard Earth model constants.
MU_EARTH_M3_S2 = 3.986004418e14
EARTH_EQUATORIAL_RADIUS_M = 6_378_137.0

# Discrete units used by the scheduling model.
TIME_SLOT_SECONDS = 600  # 10 minutes per slot
DV_UNIT_MPS = 10  # 1 model delta-v unit = 10 m/s


def radius_from_altitude_km(altitude_km: float) -> float:
    return EARTH_EQUATORIAL_RADIUS_M + altitude_km * 1_000.0


def circular_velocity_mps(radius_m: float) -> float:
    return math.sqrt(MU_EARTH_M3_S2 / radius_m)


def hohmann_delta_v_mps(r1_m: float, r2_m: float) -> float:
    v1 = circular_velocity_mps(r1_m)
    v2 = circular_velocity_mps(r2_m)
    dv1 = v1 * (math.sqrt((2.0 * r2_m) / (r1_m + r2_m)) - 1.0)
    dv2 = v2 * (1.0 - math.sqrt((2.0 * r1_m) / (r1_m + r2_m)))
    return abs(dv1) + abs(dv2)


def hohmann_time_of_flight_s(r1_m: float, r2_m: float) -> float:
    a_transfer = 0.5 * (r1_m + r2_m)
    return math.pi * math.sqrt((a_transfer**3) / MU_EARTH_M3_S2)


def orbital_period_s(radius_m: float) -> float:
    return 2.0 * math.pi * math.sqrt((radius_m**3) / MU_EARTH_M3_S2)


def to_time_slots(duration_s: float) -> int:
    return max(1, int(round(duration_s / TIME_SLOT_SECONDS)))


def to_dv_units(delta_v_mps: float) -> int:
    return max(1, int(round(delta_v_mps / DV_UNIT_MPS)))
