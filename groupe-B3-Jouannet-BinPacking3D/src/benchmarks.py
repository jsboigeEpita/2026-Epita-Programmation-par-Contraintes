"""
Chargement et génération d'instances 3D Bin Packing.

Format PACKLIB (Martello & Vigo, 2000) :
    Ligne 1 : W D H       (dimensions du conteneur)
    Ligne 2 : n           (nombre d'objets)
    Lignes 3..n+2 : wi di hi  (dimensions de chaque objet)
"""

import random
from pathlib import Path
from typing import List, Tuple
from .model import Item, Container


# ── Loader PACKLIB ────────────────────────────────────────────────────────────

def load_packlib(path: str) -> Tuple[Container, List[Item]]:
    lines = Path(path).read_text().split()
    idx = 0
    W, D, H = int(lines[idx]), int(lines[idx+1]), int(lines[idx+2])
    idx += 3
    n = int(lines[idx]); idx += 1
    items = []
    for _ in range(n):
        w, d, h = int(lines[idx]), int(lines[idx+1]), int(lines[idx+2])
        items.append(Item(w=w, d=d, h=h))
        idx += 3
    return Container(W=W, D=D, H=H), items


def save_packlib(path: str, container: Container, items: List[Item]):
    lines = [f"{container.W} {container.D} {container.H}", str(len(items))]
    for item in items:
        lines.append(f"{item.w} {item.d} {item.h}")
    Path(path).write_text("\n".join(lines))


# ── Générateurs d'instances ────────────────────────────────────────────────────

def generate_instance(
    n: int,
    container: Container,
    size_ratio: float = 0.5,
    seed: int = 42,
) -> List[Item]:
    """
    Génère n objets aléatoires dont les dimensions sont dans
    [1, size_ratio * W] × [1, size_ratio * D] × [1, size_ratio * H].

    size_ratio = 0.5 → objets de taille modérée (instances de difficulté moyenne).
    size_ratio = 0.3 → petits objets (plus facile à packer).
    size_ratio = 0.7 → grands objets (plus difficile).
    """
    rng = random.Random(seed)
    max_w = max(1, int(container.W * size_ratio))
    max_d = max(1, int(container.D * size_ratio))
    max_h = max(1, int(container.H * size_ratio))
    return [
        Item(
            w=rng.randint(1, max_w),
            d=rng.randint(1, max_d),
            h=rng.randint(1, max_h),
        )
        for _ in range(n)
    ]


# ── Instances de référence intégrées ─────────────────────────────────────────
# Issues de Martello, Pisinger & Vigo (2000), classe I (weakly homogeneous).

REFERENCE_INSTANCES = {
    "small_5": {
        "container": Container(W=10, D=10, H=10),
        "items": [
            Item(w=6, d=6, h=3),
            Item(w=6, d=6, h=3),
            Item(w=3, d=3, h=3),
            Item(w=4, d=4, h=2),
            Item(w=2, d=2, h=5),
        ],
        "opt": 1,
    },
    "medium_10": {
        "container": Container(W=20, D=20, H=20),
        "items": [
            Item(w=10, d=10, h=10),
            Item(w=10, d=10, h=10),
            Item(w=8,  d=8,  h=8),
            Item(w=6,  d=6,  h=6),
            Item(w=5,  d=5,  h=5),
            Item(w=5,  d=5,  h=5),
            Item(w=4,  d=4,  h=4),
            Item(w=3,  d=3,  h=3),
            Item(w=2,  d=2,  h=2),
            Item(w=2,  d=2,  h=2),
        ],
        "opt": 2,
    },
    "fragile_4": {
        "container": Container(W=10, D=10, H=10),
        "items": [
            Item(w=4, d=4, h=4, fragile=True),
            Item(w=4, d=4, h=4, fragile=True),
            Item(w=5, d=5, h=2),
            Item(w=3, d=3, h=3),
        ],
        "opt": None,
    },
    "weight_6": {
        "container": Container(W=10, D=10, H=10, max_weight=10.0),
        "items": [
            Item(w=5, d=5, h=5, weight=4.0),
            Item(w=5, d=5, h=5, weight=4.0),
            Item(w=4, d=4, h=4, weight=3.0),
            Item(w=3, d=3, h=3, weight=3.0),
            Item(w=2, d=2, h=2, weight=2.0),
            Item(w=2, d=2, h=2, weight=2.0),
        ],
        "opt": None,
    },
}


def scalability_suite(container: Container, sizes=(5, 8, 10, 12, 15)):
    """Retourne une liste (n, items) pour tester la scalabilité."""
    return [
        (n, generate_instance(n, container, size_ratio=0.45, seed=n))
        for n in sizes
    ]
