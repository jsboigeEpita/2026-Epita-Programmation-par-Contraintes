"""Générateurs d'instances synthétiques pour le Winner Determination Problem.

Deux distributions sont implémentées, inspirées du Combinatorial Auction Test
Suite (CATS, Leyton-Brown et al., 2000) :

    - random  : bundles aléatoires de taille variable, prix avec synergie.
    - regions : items disposés sur une grille 2D, bundles = rectangles
                connexes (modélise des enchères géographiques type spectre).

Convention XOR : toutes les offres d'un même bidder forment automatiquement
un groupe XOR (le bidder ne peut remporter qu'une seule de ses offres).
"""

from __future__ import annotations

import random
from typing import Optional

from .instance import Bid, Budget, Instance


def _build_xor_groups_per_bidder(bids: list[Bid]) -> list[list[int]]:
    """Construit un groupe XOR par bidder ayant déposé >= 2 offres.

    Convention : **un seul** groupe XOR par bidder. Cela définit le
    langage d'offres comme **XOR par bidder** (Nisan 2000, §3) — chaque
    bidder peut gagner au plus une de ses offres. Les bidders sont
    indépendants (agrégation implicite par OR à l'échelle de l'enchère,
    propriété structurelle, pas un opérateur du langage).

    Cette convention exclut volontairement le langage **OR-of-XOR**
    (plusieurs clauses XOR par bidder combinées par OR) qui exigerait
    de partitionner les offres d'un bidder en plusieurs groupes.
    """
    groups: dict[str, list[int]] = {}
    for b in bids:
        groups.setdefault(b.bidder, []).append(b.id)
    return [sorted(ids) for ids in groups.values() if len(ids) >= 2]


def _price_with_synergy(
    item_values: dict[str, float],
    bundle: frozenset[str],
    synergy: float,
) -> float:
    """Prix d'une offre = somme des valeurs item + bonus de synergie.

    Formule CATS-like : price = (sum values) * (1 + synergy * (|bundle| - 1)).
    Avec synergy = 0  : pas de synergie (prix additif).
    Avec synergy > 0  : complémentarité (le tout vaut plus que la somme).
    """
    base = sum(item_values[i] for i in bundle)
    return round(base * (1.0 + synergy * (len(bundle) - 1)), 2)


def generate_random_instance(
    n_items: int,
    n_bids: int,
    n_bidders: int,
    avg_bundle_size: float = 3.0,
    max_bundle_size: Optional[int] = None,
    synergy: float = 0.2,
    item_value_range: tuple[float, float] = (10.0, 100.0),
    max_bids_per_bidder: Optional[int] = None,
    seed: Optional[int] = None,
    name: Optional[str] = None,
) -> Instance:
    """Génère une instance WDP aléatoire.

    Args:
        n_items: nombre d'items à vendre.
        n_bids: nombre total d'offres.
        n_bidders: nombre de soumissionnaires distincts.
        avg_bundle_size: taille moyenne d'un bundle (loi de Poisson tronquée).
        max_bundle_size: taille max d'un bundle (par défaut min(n_items, 10)).
        synergy: facteur de complémentarité (>=0). 0.2 = +20% par item suppl.
        item_value_range: valeurs intrinsèques des items (uniforme).
        max_bids_per_bidder: nombre max d'offres par bidder. None = pas de cap.
        seed: graine pour la reproductibilité.
        name: nom de l'instance.

    Returns:
        Instance contenant n_items, n_bidders, n_bids bids, et des groupes XOR
        construits automatiquement par bidder.
    """
    rng = random.Random(seed)
    if max_bundle_size is None:
        max_bundle_size = min(n_items, 10)

    items = [f"i{k}" for k in range(n_items)]
    bidders = [f"b{k}" for k in range(n_bidders)]
    item_values = {i: rng.uniform(*item_value_range) for i in items}

    # Compteur d'offres par bidder pour respecter max_bids_per_bidder
    bidder_count: dict[str, int] = {b: 0 for b in bidders}

    bids: list[Bid] = []
    attempts = 0
    max_attempts = n_bids * 20

    while len(bids) < n_bids and attempts < max_attempts:
        attempts += 1
        # Choisir un bidder respectant le cap
        eligible = [
            b for b in bidders
            if max_bids_per_bidder is None or bidder_count[b] < max_bids_per_bidder
        ]
        if not eligible:
            break
        bidder = rng.choice(eligible)

        # Tirer une taille de bundle (Poisson tronquée à [1, max_bundle_size])
        k = max(1, min(max_bundle_size, int(rng.gauss(avg_bundle_size, 1.0))))
        bundle = frozenset(rng.sample(items, k))

        price = _price_with_synergy(item_values, bundle, synergy)
        bids.append(Bid(id=len(bids), bidder=bidder, items=bundle, price=price))
        bidder_count[bidder] += 1

    xor_groups = _build_xor_groups_per_bidder(bids)

    return Instance(
        name=name or f"random_{n_items}x{n_bids}_seed{seed}",
        items=items,
        bidders=bidders,
        bids=bids,
        budget=Budget(),
        xor_groups=xor_groups,
    )


def generate_regions_instance(
    grid_height: int,
    grid_width: int,
    n_bids: int,
    n_bidders: int,
    max_rect_size: int = 3,
    synergy: float = 0.3,
    item_value_range: tuple[float, float] = (10.0, 100.0),
    max_bids_per_bidder: Optional[int] = None,
    seed: Optional[int] = None,
    name: Optional[str] = None,
) -> Instance:
    """Génère une instance WDP de type 'regions' (CATS-like).

    Les items sont disposés sur une grille 2D ``grid_height x grid_width``.
    Chaque bid est un rectangle connexe d'items adjacents — modèle classique
    des enchères de spectre télécom où les fréquences/zones géographiques
    voisines ont une forte valeur conjointe.

    Args:
        grid_height: hauteur de la grille (lignes).
        grid_width: largeur de la grille (colonnes).
        n_bids: nombre total d'offres.
        n_bidders: nombre de soumissionnaires distincts.
        max_rect_size: dimension max d'un rectangle (hauteur ou largeur).
        synergy: facteur de complémentarité.
        item_value_range: valeurs intrinsèques des items (uniforme).
        max_bids_per_bidder: nombre max d'offres par bidder.
        seed: graine pour la reproductibilité.
        name: nom de l'instance.

    Returns:
        Instance avec ``grid_height * grid_width`` items, bundles rectangulaires
        et groupes XOR automatiques par bidder.
    """
    rng = random.Random(seed)

    def item_id(r: int, c: int) -> str:
        return f"r{r}c{c}"

    items = [item_id(r, c) for r in range(grid_height) for c in range(grid_width)]
    bidders = [f"b{k}" for k in range(n_bidders)]
    item_values = {i: rng.uniform(*item_value_range) for i in items}

    bidder_count: dict[str, int] = {b: 0 for b in bidders}
    bids: list[Bid] = []
    attempts = 0
    max_attempts = n_bids * 20

    while len(bids) < n_bids and attempts < max_attempts:
        attempts += 1
        eligible = [
            b for b in bidders
            if max_bids_per_bidder is None or bidder_count[b] < max_bids_per_bidder
        ]
        if not eligible:
            break
        bidder = rng.choice(eligible)

        # Coin haut-gauche aléatoire + dimensions aléatoires
        h = rng.randint(1, max_rect_size)
        w = rng.randint(1, max_rect_size)
        r0 = rng.randint(0, grid_height - h)
        c0 = rng.randint(0, grid_width - w)

        bundle = frozenset(
            item_id(r, c)
            for r in range(r0, r0 + h)
            for c in range(c0, c0 + w)
        )

        price = _price_with_synergy(item_values, bundle, synergy)
        bids.append(Bid(id=len(bids), bidder=bidder, items=bundle, price=price))
        bidder_count[bidder] += 1

    xor_groups = _build_xor_groups_per_bidder(bids)

    return Instance(
        name=name or f"regions_{grid_height}x{grid_width}_{n_bids}b_seed{seed}",
        items=items,
        bidders=bidders,
        bids=bids,
        budget=Budget(),
        xor_groups=xor_groups,
    )
