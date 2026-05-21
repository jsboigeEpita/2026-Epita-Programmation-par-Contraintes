from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Maneuver:
    idx: int
    module: str
    phase: str
    mission_regime: str
    lane: int
    orbit_from_km: int
    orbit_to_km: int
    base_delta_v_mps: int
    base_time_s: int
    window_open: int
    window_close: int
    comm_open: int
    comm_close: int
    duration_fast: int
    duration_eco: int
    dv_fast: int
    dv_eco: int

    @property
    def name(self) -> str:
        return f"{self.module}:{self.phase}"

    @property
    def earliest_start(self) -> int:
        return max(self.window_open, self.comm_open)

    @property
    def latest_end(self) -> int:
        return min(self.window_close, self.comm_close)

    @property
    def min_duration(self) -> int:
        return min(self.duration_fast, self.duration_eco)

    @property
    def max_duration(self) -> int:
        return max(self.duration_fast, self.duration_eco)


@dataclass(frozen=True)
class Precedence:
    pred: int
    succ: int
    lag: int = 0


@dataclass(frozen=True)
class SafetyConflict:
    left: int
    right: int
    separation: int = 0


@dataclass(frozen=True)
class OrbitalInstance:
    name: str
    horizon: int
    maneuvers: List[Maneuver]
    precedences: List[Precedence]
    safety_conflicts: List[SafetyConflict]
    total_fuel_budget: int
    concurrent_dv_capacity: int
    metadata: Dict[str, Any] | None = None

    def n(self) -> int:
        return len(self.maneuvers)

    def validate(self) -> Tuple[bool, str]:
        if self.horizon <= 0:
            return False, "horizon must be > 0"
        if not self.maneuvers:
            return False, "instance has no maneuvers"
        n = len(self.maneuvers)
        for m in self.maneuvers:
            if not (0 <= m.idx < n):
                return False, f"maneuver idx out of range: {m.idx}"
            if m.earliest_start >= m.latest_end:
                return False, f"empty feasible window for maneuver {m.name}"
            if m.min_duration <= 0 or m.max_duration <= 0:
                return False, f"non-positive duration for maneuver {m.name}"
            if m.dv_fast <= 0 or m.dv_eco <= 0:
                return False, f"non-positive delta-v for maneuver {m.name}"
            if m.orbit_from_km <= 0 or m.orbit_to_km <= 0:
                return False, f"invalid orbit altitudes for maneuver {m.name}"
            if m.base_delta_v_mps <= 0 or m.base_time_s <= 0:
                return False, f"invalid orbital baseline values for maneuver {m.name}"
        for edge in self.precedences:
            if not (0 <= edge.pred < n and 0 <= edge.succ < n):
                return False, "precedence index out of range"
            if edge.pred == edge.succ:
                return False, "self precedence edge"
        for c in self.safety_conflicts:
            if not (0 <= c.left < n and 0 <= c.right < n):
                return False, "safety conflict index out of range"
            if c.left == c.right:
                return False, "self safety conflict"
        if self.concurrent_dv_capacity <= 0:
            return False, "concurrent_dv_capacity must be > 0"
        if self.total_fuel_budget <= 0:
            return False, "total_fuel_budget must be > 0"
        return True, "ok"
