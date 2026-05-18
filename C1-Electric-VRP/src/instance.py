from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from math import sqrt, ceil
import numpy as np

DEPOT = 0
CUSTOMER = 1
STATION = 2

# Integer scaling for CP-SAT
DIST_SCALE = 10      # 1 unit = 0.1 km  (coords in [0,100] → max dist ≈ 1414)
ENERGY_SCALE = 100   # 1 unit = 0.01 kWh (40 kWh battery → 4000 units)

# Slope scaling: slope stored as integer permille (1 unit = 0.001 = 0.1%)
SLOPE_SCALE = 1000


@dataclass
class EVRPInstance:
    """
    Electric VRP instance.

    Node layout:
      index 0          : depot
      indices 1..C     : customers  (C = n_customers)
      indices C+1..C+S : charging stations (S = n_stations)

    All distances and energies stored as scaled integers for CP-SAT.

    Slope model (optional):
      slope_matrix[i][j] in [-SLOPE_SCALE, +SLOPE_SCALE] (permille, integer).
      Positive = uphill i→j, negative = downhill.
      Energy multiplier = 1 + slope_factor * slope_matrix[i][j] / SLOPE_SCALE
    """

    coords: List[Tuple[float, float]]       # (x, y) for each node
    node_types: List[int]                   # DEPOT / CUSTOMER / STATION
    demands: List[int]                      # delivery demand (0 for depot/station)
    time_windows: List[Tuple[int, int]]     # (earliest, latest) in minutes
    service_times: List[int]                # minutes spent at each node

    n_vehicles: int
    vehicle_capacity: int                   # max payload per vehicle

    battery_capacity: int                   # ENERGY_SCALE units (e.g. 4000 = 40.00 kWh)
    consumption_rate: int                   # ENERGY_SCALE units per DIST_SCALE unit, empty load
    load_sensitivity: float = 0.1          # extra consumption fraction per full load

    speed_kmh: float = 60.0                # km/h for travel-time computation

    # Slope model fields (None = flat terrain)
    slope_matrix: Optional[List[List[int]]] = None   # permille integers per arc
    slope_factor: float = 0.15             # max energy multiplier at max slope

    def __post_init__(self):
        n = len(self.coords)
        self.n_nodes = n
        self.customer_indices = [i for i, t in enumerate(self.node_types) if t == CUSTOMER]
        self.station_indices  = [i for i, t in enumerate(self.node_types) if t == STATION]
        self.n_customers = len(self.customer_indices)
        self.n_stations  = len(self.station_indices)

        # Ensure slope_matrix is always n×n before building energy matrix
        if self.slope_matrix is None:
            self.slope_matrix = [[0] * n for _ in range(n)]

        self._dist   = self._build_dist_matrix(n)
        self._energy = self._build_energy_matrix(n)
        self._time   = self._build_time_matrix(n)

    # ── matrix builders ───────────────────────────────────────────────────────

    def _build_dist_matrix(self, n: int) -> List[List[int]]:
        d = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    dx = self.coords[i][0] - self.coords[j][0]
                    dy = self.coords[i][1] - self.coords[j][1]
                    d[i][j] = int(round(sqrt(dx ** 2 + dy ** 2) * DIST_SCALE))
        return d

    def _build_energy_matrix(self, n: int) -> List[List[int]]:
        """Base energy (empty load) in ENERGY_SCALE units, with slope factor applied."""
        e = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    base = self.consumption_rate * self._dist[i][j] // DIST_SCALE
                    slope_pct = self.slope_matrix[i][j]  # permille integer
                    multiplier = 1.0 + self.slope_factor * slope_pct / SLOPE_SCALE
                    e[i][j] = max(0, int(round(base * multiplier)))
        return e

    def _build_time_matrix(self, n: int) -> List[List[int]]:
        t = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    real_km = self._dist[i][j] / DIST_SCALE
                    t[i][j] = int(ceil(real_km / self.speed_kmh * 60))
        return t

    # ── accessors ─────────────────────────────────────────────────────────────

    def dist(self, i: int, j: int) -> int:
        return self._dist[i][j]

    def energy(self, i: int, j: int, load: int = 0) -> int:
        """Energy (ENERGY_SCALE units) to drive i→j carrying given load.

        Incorporates slope (already baked into _energy[i][j] at build time)
        and an optional load-sensitivity bonus.
        """
        base = self._energy[i][j]  # already includes slope factor
        bonus = int(base * self.load_sensitivity * load / max(self.vehicle_capacity, 1))
        return base + bonus

    def travel_time(self, i: int, j: int) -> int:
        """Travel time in minutes."""
        return self._time[i][j]

    def total_demand(self) -> int:
        return sum(self.demands)

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def random(
        cls,
        n_customers: int = 10,
        n_stations: int = 3,
        seed: int = 42,
        n_vehicles: int = 3,
        vehicle_capacity: int = 100,
        with_slope: bool = True,
    ) -> EVRPInstance:
        """Generate a small random EVRP instance with optional terrain slope."""
        rng = np.random.default_rng(seed)

        coords        = [(50.0, 50.0)]
        node_types    = [DEPOT]
        demands       = [0]
        time_windows  = [(0, 1440)]
        service_times = [0]

        for _ in range(n_customers):
            coords.append((float(rng.uniform(5, 95)), float(rng.uniform(5, 95))))
            node_types.append(CUSTOMER)
            demands.append(int(rng.integers(10, 40)))
            tw_open = int(rng.integers(0, 600))
            time_windows.append((tw_open, tw_open + int(rng.integers(120, 600))))
            service_times.append(15)

        for _ in range(n_stations):
            coords.append((float(rng.uniform(10, 90)), float(rng.uniform(10, 90))))
            node_types.append(STATION)
            demands.append(0)
            time_windows.append((0, 1440))
            service_times.append(0)

        n = 1 + n_customers + n_stations
        # Random slopes in [-500, +500] permille (±50% of slope_factor)
        slope_matrix = None
        if with_slope:
            raw = rng.integers(-500, 500, size=(n, n))
            np.fill_diagonal(raw, 0)
            # Slopes are anti-symmetric: downhill one way = uphill the other
            for i in range(n):
                for j in range(i + 1, n):
                    raw[j][i] = -raw[i][j]
            slope_matrix = raw.tolist()

        return cls(
            coords=coords,
            node_types=node_types,
            demands=demands,
            time_windows=time_windows,
            service_times=service_times,
            n_vehicles=n_vehicles,
            vehicle_capacity=vehicle_capacity,
            battery_capacity=4000,   # 40.00 kWh
            consumption_rate=2,      # 0.02 kWh per 0.1 km = 0.2 kWh/km (realistic EV)
            load_sensitivity=0.1,
            slope_matrix=slope_matrix,
            slope_factor=0.15,
        )

    @classmethod
    def schneider_like(
        cls,
        n_customers: int = 10,
        seed: int = 42,
        with_slope: bool = False,
    ) -> "EVRPInstance":
        """
        Instance synthétique calée sur les paramètres de Schneider et al. (2014).

        Paramètres repris du papier :
          - Grille 100×100 km, dépôt au centre
          - ~ratio 1 station pour 3 clients (arrondi)
          - Capacité 200 unités (C1/R1 de Solomon)
          - Batterie 77.75 kWh, consommation 1 kWh/km (Schneider 2014, Table 1)
          - Flotte : ceil(n_customers / 5) véhicules
          - Fenêtres horaires type Solomon (horizon 1236 min)
          - Demandes uniformes [1, 40]
          - Service time 90 min (standard Solomon)
        """
        import math
        rng = np.random.default_rng(seed)
        n_stations = max(1, n_customers // 3)
        n_vehicles = math.ceil(n_customers / 5)

        coords        = [(50.0, 50.0)]
        node_types    = [DEPOT]
        demands       = [0]
        time_windows  = [(0, 1236)]
        service_times = [0]

        for _ in range(n_customers):
            coords.append((float(rng.uniform(0, 100)), float(rng.uniform(0, 100))))
            node_types.append(CUSTOMER)
            demands.append(int(rng.integers(1, 40)))
            tw_open = int(rng.integers(0, 900))
            time_windows.append((tw_open, min(1236, tw_open + int(rng.integers(90, 400)))))
            service_times.append(90)

        for _ in range(n_stations):
            coords.append((float(rng.uniform(0, 100)), float(rng.uniform(0, 100))))
            node_types.append(STATION)
            demands.append(0)
            time_windows.append((0, 1236))
            service_times.append(0)

        n = 1 + n_customers + n_stations
        slope_matrix = None
        if with_slope:
            raw = rng.integers(-300, 300, size=(n, n))
            np.fill_diagonal(raw, 0)
            for i in range(n):
                for j in range(i + 1, n):
                    raw[j][i] = -raw[i][j]
            slope_matrix = raw.tolist()

        return cls(
            coords=coords,
            node_types=node_types,
            demands=demands,
            time_windows=time_windows,
            service_times=service_times,
            n_vehicles=n_vehicles,
            vehicle_capacity=200,
            battery_capacity=7775,   # 77.75 kWh × 100  (Schneider 2014, Table 1)
            consumption_rate=10,     # 1 kWh/km × ENERGY_SCALE / DIST_SCALE = 100/10 = 10
            load_sensitivity=0.0,    # Schneider uses load-independent consumption
            slope_matrix=slope_matrix,
            slope_factor=0.15,
        )
