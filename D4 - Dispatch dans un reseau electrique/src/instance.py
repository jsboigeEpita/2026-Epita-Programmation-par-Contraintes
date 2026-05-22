"""Data model for the Economic Dispatch problem.

A `PowerNetwork` groups buses (consumption nodes), transmission lines, and
generators (thermal + renewable). All numeric quantities are stored in
engineering units (MW, $/h, $/MWh) and converted to integers by the solvers.

Two factory functions provide ready-to-use test cases:

- `three_bus_toy()`         — 3 buses, 3 thermal generators (pedagogic)
- `six_bus_congested()`     — 6 buses, line capacity bottleneck
- `ieee14()`                — IEEE 14-bus test case (5 generators)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Literal


GenKind = Literal["thermal", "wind", "solar"]


@dataclass
class Generator:
    """A power plant attached to a bus.

    Thermal units carry a convex quadratic cost  c(P) = a + b·P + c·P²  ($/h)
    plus unit-commitment parameters (start-up cost, minimum up/down time,
    ramp rates). Renewable units (wind/solar) have zero marginal cost and
    a time-varying availability handled at the scenario level.
    """

    id: str
    bus: int
    p_min: float          # MW, minimum stable output when ON
    p_max: float          # MW, maximum output
    cost_a: float = 0.0   # $/h fixed term (when ON)
    cost_b: float = 0.0   # $/MWh linear term
    cost_c: float = 0.0   # $/MWh² quadratic term
    startup_cost: float = 0.0   # $ per cold start
    shutdown_cost: float = 0.0  # $ per shutdown
    min_up: int = 1       # hours
    min_down: int = 1     # hours
    ramp_up: float = 1e9      # MW/h
    ramp_down: float = 1e9    # MW/h
    init_state: int = 1   # 1 = ON at t = -1, 0 = OFF
    init_power: float = 0.0
    kind: GenKind = "thermal"

    def cost(self, p: float) -> float:
        """Operating cost at output P (MW), when the unit is ON."""
        return self.cost_a + self.cost_b * p + self.cost_c * p * p


@dataclass
class Bus:
    """A node of the grid with a (possibly zero) base load in MW."""
    id: int
    name: str = ""
    load: float = 0.0


@dataclass
class Line:
    """A transmission line connecting two buses.

    Uses a **transportation model**: flow is a free variable in
    [−capacity, +capacity], conserved at each node. This is the standard
    simplification when reactance data is unavailable and matches the
    classical economic-dispatch formulation in Wood & Wollenberg.
    """
    from_bus: int
    to_bus: int
    capacity: float       # MW (symmetric)


@dataclass
class PowerNetwork:
    """A complete power system: buses + lines + generators."""

    buses: List[Bus]
    lines: List[Line]
    generators: List[Generator]
    name: str = ""
    base_mva: float = 100.0
    reserve_fraction: float = 0.10   # spinning reserve as a fraction of total load

    def total_load(self) -> float:
        return sum(b.load for b in self.buses)

    def total_capacity(self) -> float:
        return sum(g.p_max for g in self.generators)

    def thermal_generators(self) -> List[Generator]:
        return [g for g in self.generators if g.kind == "thermal"]

    def renewable_generators(self) -> List[Generator]:
        return [g for g in self.generators if g.kind in ("wind", "solar")]

    def gen_at_bus(self, b: int) -> List[Generator]:
        return [g for g in self.generators if g.bus == b]

    def lines_at_bus(self, b: int) -> List[tuple[int, Line]]:
        """Return (line_index, line) for all lines touching bus b."""
        return [(idx, ln) for idx, ln in enumerate(self.lines)
                if ln.from_bus == b or ln.to_bus == b]


# --------------------------------------------------------------------------- #
# Toy / benchmark instances
# --------------------------------------------------------------------------- #

def three_bus_toy(peak_load: float = 300.0) -> PowerNetwork:
    """A small 3-bus, 3-generator system used for the introductory example.

         G1(cheap, slow)        G2(medium)
             |                       |
            B0 ----L01---- B1 ----L12---- B2
                          load                load
                          120 MW              180 MW
                                              + G3(peaker)
    """
    buses = [
        Bus(0, "Power-Plant",      0.0),
        Bus(1, "City-A",         120.0 * peak_load / 300.0),
        Bus(2, "City-B",         180.0 * peak_load / 300.0),
    ]
    lines = [
        Line(0, 1, capacity=280.0),
        Line(1, 2, capacity=220.0),
    ]
    generators = [
        Generator(id="G1-base",   bus=0, p_min=50,  p_max=250,
                  cost_a=300, cost_b=18.0, cost_c=0.0040,
                  startup_cost=800, min_up=4, min_down=2,
                  ramp_up=80, ramp_down=80, init_state=1, init_power=120),
        Generator(id="G2-mid",    bus=1, p_min=20,  p_max=120,
                  cost_a=200, cost_b=25.0, cost_c=0.0080,
                  startup_cost=400, min_up=2, min_down=1,
                  ramp_up=60, ramp_down=60),
        Generator(id="G3-peaker", bus=2, p_min=10,  p_max=80,
                  cost_a=100, cost_b=40.0, cost_c=0.0150,
                  startup_cost=150, min_up=1, min_down=1,
                  ramp_up=80, ramp_down=80),
    ]
    return PowerNetwork(buses=buses, lines=lines, generators=generators,
                        name="3-bus-toy", reserve_fraction=0.10)


def six_bus_congested() -> PowerNetwork:
    """A 6-bus instance built so that the cheapest line becomes the binding
    constraint at peak load. Useful to showcase that the optimal dispatch is
    not the merit-order dispatch when transmission is limited.
    """
    buses = [
        Bus(0, "North-Plant",   0.0),
        Bus(1, "North-City",   90.0),
        Bus(2, "Mid-Hub",      40.0),
        Bus(3, "South-Hub",    50.0),
        Bus(4, "South-City",  140.0),
        Bus(5, "Peaker-Site",  20.0),
    ]
    lines = [
        Line(0, 1, capacity=150.0),
        Line(0, 2, capacity= 90.0),   # bottleneck north -> south
        Line(1, 2, capacity= 80.0),
        Line(2, 3, capacity= 70.0),   # critical link
        Line(3, 4, capacity=120.0),
        Line(3, 5, capacity= 60.0),
        Line(4, 5, capacity= 60.0),
    ]
    generators = [
        # Cheap baseload in the North
        Generator("G-coal-N", bus=0, p_min=80, p_max=300,
                  cost_a=400, cost_b=14.0, cost_c=0.0030,
                  startup_cost=1200, min_up=6, min_down=3,
                  ramp_up=60, ramp_down=60, init_state=1, init_power=200),
        # Mid-merit gas
        Generator("G-gas-M",  bus=2, p_min=30, p_max=150,
                  cost_a=250, cost_b=28.0, cost_c=0.0070,
                  startup_cost=500, min_up=2, min_down=1,
                  ramp_up=80, ramp_down=80),
        # Expensive peaker close to demand
        Generator("G-peak-S", bus=4, p_min=10, p_max=90,
                  cost_a=120, cost_b=55.0, cost_c=0.0200,
                  startup_cost=100, min_up=1, min_down=1,
                  ramp_up=90, ramp_down=90),
        Generator("G-peak-X", bus=5, p_min=10, p_max=60,
                  cost_a=100, cost_b=60.0, cost_c=0.0250,
                  startup_cost=80,  min_up=1, min_down=1,
                  ramp_up=60, ramp_down=60),
    ]
    return PowerNetwork(buses=buses, lines=lines, generators=generators,
                        name="6-bus-congested", reserve_fraction=0.10)


def ieee14() -> PowerNetwork:
    """IEEE 14-bus test case (simplified for economic dispatch).

    Five generators, fourteen buses, and twenty branches. Loads and generator
    parameters follow the classical IEEE 14-bus data from the University of
    Washington archive (https://labs.ece.uw.edu/pstca/pf14/pg_tca14bus.htm),
    scaled to MW. The line transport capacities are placeholders representative
    of the network topology.
    """
    loads = {
        0: 0.0,   1: 21.7, 2: 94.2, 3: 47.8, 4:  7.6,
        5: 11.2,  6:  0.0, 7:  0.0, 8: 29.5, 9:  9.0,
       10:  3.5, 11:  6.1,12: 13.5,13: 14.9,
    }
    buses = [Bus(i, f"Bus-{i+1}", loads[i]) for i in range(14)]

    # (from, to, capacity MW)
    branches = [
        (0,1,160), (0,4,160), (1,2,160), (1,3,100), (1,4, 80),
        (2,3,100), (3,4,100), (4,5, 80), (5,10, 50), (5,11, 50),
        (5,12, 60), (3,6, 80), (3,8, 80), (6,7, 60), (6,8, 60),
        (8,9, 50), (8,13, 60), (9,10, 50), (11,12, 30), (12,13, 30),
    ]
    lines = [Line(f, t, capacity=c) for (f, t, c) in branches]

    # Five generators (buses 0, 1, 2, 5, 7 in 0-indexed)
    generators = [
        Generator("G1", bus=0, p_min=50,  p_max=332,
                  cost_a=400, cost_b=20.0, cost_c=0.0043,
                  startup_cost=1500, min_up=5, min_down=3,
                  ramp_up=80, ramp_down=80, init_state=1, init_power=200),
        Generator("G2", bus=1, p_min=20,  p_max=140,
                  cost_a=300, cost_b=25.0, cost_c=0.0050,
                  startup_cost= 800, min_up=3, min_down=2,
                  ramp_up=60, ramp_down=60, init_state=1, init_power= 60),
        Generator("G3", bus=2, p_min=20,  p_max=100,
                  cost_a=200, cost_b=30.0, cost_c=0.0085,
                  startup_cost= 600, min_up=2, min_down=2,
                  ramp_up=50, ramp_down=50),
        Generator("G6", bus=5, p_min=10,  p_max= 80,
                  cost_a=150, cost_b=40.0, cost_c=0.0125,
                  startup_cost= 250, min_up=1, min_down=1,
                  ramp_up=60, ramp_down=60),
        Generator("G8", bus=7, p_min=10,  p_max= 60,
                  cost_a=100, cost_b=45.0, cost_c=0.0150,
                  startup_cost= 150, min_up=1, min_down=1,
                  ramp_up=60, ramp_down=60),
    ]
    return PowerNetwork(buses=buses, lines=lines, generators=generators,
                        name="IEEE-14", reserve_fraction=0.10)


def add_renewables(net: PowerNetwork, wind_bus: int = 1, solar_bus: int = 2,
                   wind_cap: float = 80.0, solar_cap: float = 60.0) -> PowerNetwork:
    """Append a wind farm and a solar plant to an existing network."""
    net.generators.append(
        Generator(f"WIND@{wind_bus}",  bus=wind_bus,  p_min=0, p_max=wind_cap,
                  cost_a=0, cost_b=0, cost_c=0,
                  min_up=1, min_down=1, ramp_up=wind_cap, ramp_down=wind_cap,
                  kind="wind")
    )
    net.generators.append(
        Generator(f"SOLAR@{solar_bus}", bus=solar_bus, p_min=0, p_max=solar_cap,
                  cost_a=0, cost_b=0, cost_c=0,
                  min_up=1, min_down=1, ramp_up=solar_cap, ramp_down=solar_cap,
                  kind="solar")
    )
    return net
