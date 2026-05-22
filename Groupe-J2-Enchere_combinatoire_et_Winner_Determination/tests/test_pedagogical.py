"""Tests de régression sur les trois instances pédagogiques.

Les valeurs attendues ci-dessous ont été dérivées analytiquement à la
main (cf. README) puis confirmées par CP-SAT à l'implémentation. Tout
écart signale soit un changement de modèle, soit un bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wdp.instance import Instance
from wdp.solver_cpsat import solve_wdp_cpsat
from wdp.solver_milp import solve_wdp_milp
from wdp.solver_greedy import solve_wdp_greedy
from wdp.instance import Bid, Budget
from wdp.vcg import run_vcg, run_vcg_canonical

DATA = Path(__file__).resolve().parent.parent / "data"


# ---------------------------------------------------------------------------
# Livrables 1-3 : WDP exact (CP-SAT == PLNE)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,expected_revenue",
    [
        ("toy_example", 40.0),    # David {P,L,M}
        ("with_budget", 50.0),    # Saturé par budget global
        ("with_xor",    57.0),    # Alice bid 2 + Bob bid 4
    ],
)
def test_cpsat_pedagogical(name, expected_revenue):
    inst = Instance.from_json(DATA / f"{name}.json")
    alloc = solve_wdp_cpsat(inst)
    assert alloc.status == "OPTIMAL"
    assert alloc.revenue == pytest.approx(expected_revenue, abs=1e-6)


@pytest.mark.parametrize("name", ["toy_example", "with_budget", "with_xor"])
def test_cpsat_and_milp_agree(name):
    inst = Instance.from_json(DATA / f"{name}.json")
    cp = solve_wdp_cpsat(inst)
    mip = solve_wdp_milp(inst)
    assert cp.revenue == pytest.approx(mip.revenue, abs=1e-4)


# ---------------------------------------------------------------------------
# Extension : greedy ≤ exact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["toy_example", "with_budget", "with_xor"])
def test_greedy_lower_bound(name):
    """Greedy doit produire une borne inférieure : revenue_greedy <= revenue_exact."""
    inst = Instance.from_json(DATA / f"{name}.json")
    g = solve_wdp_greedy(inst)
    cp = solve_wdp_cpsat(inst)
    # Solution greedy faisable, donc <= optimum
    assert g.revenue <= cp.revenue + 1e-6


# ---------------------------------------------------------------------------
# Livrable 5 : VCG (David paie 37 sur toy_example)
# ---------------------------------------------------------------------------

def test_vcg_toy_payment_david():
    """Sur toy_example, David gagne pour v=40 ; sans lui welfare=37 (Bob+Eve).
    Donc p_David = W_-D* - (W* - v_D) = 37 - (40 - 40) = 37."""
    inst = Instance.from_json(DATA / "toy_example.json")
    res = run_vcg(inst)
    assert "David" in res.payments
    assert res.payments["David"] == pytest.approx(37.0, abs=1e-6)
    assert res.social_welfare == pytest.approx(40.0, abs=1e-6)


@pytest.mark.parametrize("name", ["toy_example", "with_budget", "with_xor"])
def test_vcg_properties(name):
    """Les propriétés VCG (IR, losers pay 0, no-deficit) doivent passer."""
    inst = Instance.from_json(DATA / f"{name}.json")
    res = run_vcg(inst)
    v = res.verify_properties()
    assert v["individual_rationality"]["ok"], v["violations"]
    assert v["losers_pay_zero"]["ok"], v["violations"]
    assert v["no_deficit"]["ok"], v["violations"]
    assert v["optimal_solves"]["ok"], v["violations"]
    assert v["all_ok"], v["violations"]
