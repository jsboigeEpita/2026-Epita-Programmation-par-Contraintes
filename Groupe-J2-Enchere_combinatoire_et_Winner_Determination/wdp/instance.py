"""Représentation d'une instance du Winner Determination Problem (WDP).

**Langage d'offres : XOR par bidder (Nisan 2000, "Bidding and Allocation
in Combinatorial Auctions", §3).**

Chaque bidder déclare un ensemble d'offres atomiques regroupées en
**au plus une clause XOR** (au plus une de ses offres peut gagner —
encodé via ``xor_groups``). Les bidders sont indépendants : on agrège
implicitement leurs déclarations par OR (n'importe quel sous-ensemble
disjoint d'offres gagnantes, une par bidder, peut être sélectionné).

Cette agrégation OR-entre-bidders n'est pas un opérateur du langage au
sens de Nisan §3 ; c'est une propriété structurelle de toute enchère
combinatoire. Le langage à l'échelle d'un bidder est donc **XOR**, et
le théorème d'expressivité (Nisan 2000, Thm 1) garantit que cette
représentation est universelle pour des valuations de type "au plus
un bundle parmi {S_1, ..., S_n}".

Pour un langage **OR-of-XOR** (un bidder déclare plusieurs clauses XOR
combinées par OR), il faudrait que le générateur produise plusieurs
groupes XOR par bidder — ce que nous ne faisons pas.

Format JSON attendu :

{
  "name": "toy_example",
  "items": ["P", "L", "M"],
  "bidders": ["Alice", "Bob", "Carol"],
  "bids": [
    {"id": 0, "bidder": "Alice", "items": ["P", "L"], "price": 25},
    ...
  ],
  "budget": {
    "global": null,
    "per_bidder": {"Alice": 30}
  },
  "xor_groups": [[0, 1, 2], [3, 4]]
}

Notes :
    - items et bidders sont des identifiants string (lisibles en debug).
    - xor_groups est une liste explicite de groupes d'ids d'offres ;
      chaque groupe impose la contrainte "au plus une offre gagnante".
    - budget.global : plafond de dépense total (null = pas de plafond).
    - budget.per_bidder : plafond par bidder (clés manquantes = pas de plafond
      pour ce bidder).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Bid:
    """Une offre combinatoire : un bidder propose un prix pour un paquet d'items."""

    id: int
    bidder: str
    items: frozenset[str]
    price: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "bidder": self.bidder,
            "items": sorted(self.items),
            "price": self.price,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Bid":
        return cls(
            id=int(data["id"]),
            bidder=str(data["bidder"]),
            items=frozenset(data["items"]),
            price=float(data["price"]),
        )


@dataclass
class Budget:
    """Contraintes budgétaires (toutes optionnelles)."""

    global_cap: Optional[float] = None
    per_bidder: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"global": self.global_cap, "per_bidder": dict(self.per_bidder)}

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Budget":
        if data is None:
            return cls()
        return cls(
            global_cap=data.get("global"),
            per_bidder=dict(data.get("per_bidder", {})),
        )

    def is_active(self) -> bool:
        return self.global_cap is not None or len(self.per_bidder) > 0


@dataclass
class Instance:
    """Instance complète du WDP."""

    name: str
    items: list[str]
    bidders: list[str]
    bids: list[Bid]
    budget: Budget = field(default_factory=Budget)
    xor_groups: list[list[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Vérifie la cohérence interne de l'instance."""
        items_set = set(self.items)
        bidders_set = set(self.bidders)
        bid_ids = [b.id for b in self.bids]

        if len(set(bid_ids)) != len(bid_ids):
            raise ValueError("Les ids d'offres doivent être uniques.")

        for b in self.bids:
            unknown = b.items - items_set
            if unknown:
                raise ValueError(
                    f"Bid {b.id} référence des items inconnus : {sorted(unknown)}"
                )
            if b.bidder not in bidders_set:
                raise ValueError(
                    f"Bid {b.id} référence un bidder inconnu : {b.bidder!r}"
                )
            if b.price < 0:
                raise ValueError(f"Bid {b.id} a un prix négatif : {b.price}")

        bid_ids_set = set(bid_ids)
        for group in self.xor_groups:
            unknown = set(group) - bid_ids_set
            if unknown:
                raise ValueError(
                    f"xor_group {group} référence des ids inconnus : {sorted(unknown)}"
                )

        for bidder, cap in self.budget.per_bidder.items():
            if bidder not in bidders_set:
                raise ValueError(f"budget.per_bidder référence un bidder inconnu : {bidder!r}")
            if cap < 0:
                raise ValueError(f"budget.per_bidder[{bidder!r}] négatif : {cap}")

    @property
    def n_items(self) -> int:
        return len(self.items)

    @property
    def n_bids(self) -> int:
        return len(self.bids)

    @property
    def n_bidders(self) -> int:
        return len(self.bidders)

    def bids_by_bidder(self, bidder: str) -> list[Bid]:
        return [b for b in self.bids if b.bidder == bidder]

    def bids_containing(self, item: str) -> list[Bid]:
        return [b for b in self.bids if item in b.items]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "items": list(self.items),
            "bidders": list(self.bidders),
            "bids": [b.to_dict() for b in self.bids],
            "budget": self.budget.to_dict(),
            "xor_groups": [list(g) for g in self.xor_groups],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Instance":
        return cls(
            name=data["name"],
            items=list(data["items"]),
            bidders=list(data["bidders"]),
            bids=[Bid.from_dict(b) for b in data["bids"]],
            budget=Budget.from_dict(data.get("budget")),
            xor_groups=[list(g) for g in data.get("xor_groups", [])],
        )

    def to_json(self, path: str | Path, indent: int = 2) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "Instance":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)

    def summary(self) -> str:
        """Résumé textuel court pour l'affichage."""
        lines = [
            f"Instance: {self.name}",
            f"  items   : {self.n_items}",
            f"  bidders : {self.n_bidders}",
            f"  bids    : {self.n_bids}",
        ]
        if self.budget.is_active():
            lines.append(f"  budget  : {self.budget.to_dict()}")
        if self.xor_groups:
            lines.append(f"  xor     : {len(self.xor_groups)} groupe(s)")
        return "\n".join(lines)


@dataclass
class Allocation:
    """Résultat d'une résolution WDP."""

    winning_bid_ids: list[int]
    revenue: float
    status: str
    solve_time: float
    solver: str

    def to_dict(self) -> dict:
        return asdict(self)
