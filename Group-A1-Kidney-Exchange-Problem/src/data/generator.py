import random
import json

from src.core.graph import KEPGraph, Pair, Patient, Donor
from src.core.compatibility import CompatibilityChecker

BLOOD_TYPE_COMPATIBILITY = {
    'O':  ['O', 'A', 'B', 'AB'],
    'A':  ['A', 'AB'],
    'B':  ['B', 'AB'],
    'AB': ['AB'],
}
BLOOD_TYPES = ['O', 'A', 'B', 'AB']
BLOOD_FREQ = [0.44, 0.42, 0.10, 0.04]  # fréquences réelles
HLA_POOL = [f'{l}{n}' for l in ['A','B','DR'] for n in range(1, 20)]

def generate_instance(
    n_pairs: int,
    seed: int = 42,
    pra_high_ratio: float = 0.15,
    n_ndd: int = 0,
) -> dict:
    """
    Génère une instance KEP synthétique.

    Args:
        n_pairs        : Nombre de paires patient-donneur incompatibles.
        seed           : Graine aléatoire pour la reproductibilité.
        pra_high_ratio : Proportion de patients très sensibilisés (PRA > 0.8).
        n_ndd          : Nombre de donneurs altruistes (Non-Directed Donors).

    Returns:
        Dictionnaire avec clés 'pairs' et 'ndds'.
    """
    rng = random.Random(seed)
    pairs = []

    for i in range(n_pairs):
        while True:
            donor_bt   = rng.choices(BLOOD_TYPES, BLOOD_FREQ)[0]
            patient_bt = rng.choices(BLOOD_TYPES, BLOOD_FREQ)[0]
            donor_hla  = rng.sample(HLA_POOL, 6)

            if rng.random() < pra_high_ratio:
                pra          = rng.uniform(0.8, 1.0)
                n_antibodies = rng.randint(8, 15)
            else:
                pra          = rng.uniform(0.0, 0.5)
                n_antibodies = rng.randint(0, 4)

            patient_antibodies = rng.sample(HLA_POOL, n_antibodies)

            blood_incompatible = patient_bt not in BLOOD_TYPE_COMPATIBILITY[donor_bt]
            hla_incompatible   = any(ab in donor_hla for ab in patient_antibodies)

            if blood_incompatible or hla_incompatible:
                break

        pairs.append({
            "id": i,
            "donor": {
                "blood_type": donor_bt,
                "hla": donor_hla,
            },
            "patient": {
                "blood_type":     patient_bt,
                "pra":            round(pra, 2),
                "antibodies":     patient_antibodies,
                "dialysis_months": rng.randint(1, 120),
            },
        })

    # Donneurs altruistes (groupe O universel, HLA vide → compat. maximale)
    ndds = []
    for k in range(n_ndd):
        ndd_id = n_pairs + k
        # On peut varier le groupe et HLA pour des scénarios réalistes
        bt = rng.choices(BLOOD_TYPES, BLOOD_FREQ)[0]
        ndds.append({
            "id":   ndd_id,
            "donor": {
                "blood_type": bt,
                "hla": rng.sample(HLA_POOL, 4),
            },
        })

    return {"pairs": pairs, "ndds": ndds}

def build_kep_graph(
    instance: dict,
    max_cycle_size: int = 3,
    max_chain_length: int = 3,
) -> KEPGraph:
    """
    Construit un KEPGraph complet depuis un dictionnaire d'instance.

    Args:
        instance        : Sortie de generate_instance() ou load_csplib_instance().
        max_cycle_size  : Taille max des cycles.
        max_chain_length: Longueur max des chaînes altruistes.

    Returns:
        KEPGraph avec paires, NDD et arcs de compatibilité construits.
    """
    checker = CompatibilityChecker()
    kep = KEPGraph(max_cycle_size=max_cycle_size, max_chain_length=max_chain_length)

    for r in instance["pairs"]:
        donor = Donor(
            id=r["id"],
            blood_type=r["donor"]["blood_type"],
            hla_antigens=r["donor"]["hla"],
        )
        patient = Patient(
            id=r["id"],
            blood_type=r["patient"]["blood_type"],
            pra=r["patient"]["pra"],
            hla_antibodies=r["patient"]["antibodies"],
            time_on_dialysis=r["patient"]["dialysis_months"],
        )
        kep.add_pair(Pair(id=r["id"], patient=patient, donor=donor))

    for ndd_data in instance.get("ndds", []):
        ndd_donor = Donor(
            id=ndd_data["id"],
            blood_type=ndd_data["donor"]["blood_type"],
            hla_antigens=ndd_data["donor"]["hla"],
        )
        ndd_pair = Pair(
            id=ndd_data["id"],
            patient=None,
            donor=ndd_donor,
            is_altruistic=True,
        )
        kep.add_pair(ndd_pair)

    kep.build_compatibility_arcs(checker)

    return kep

def make_random_kep(
    n_pairs: int = 20,
    n_ndd: int = 2,
    seed: int = 42,
    max_cycle_size: int = 3,
    max_chain_length: int = 3,
    pra_high_ratio: float = 0.15,
) -> KEPGraph:
    """
    Raccourci : génère une instance aléatoire et retourne le KEPGraph prêt à l'emploi.

    Example:
        kep = make_random_kep(n_pairs=30, n_ndd=3, seed=0)
        print(kep)
    """
    instance = generate_instance(
        n_pairs=n_pairs,
        seed=seed,
        pra_high_ratio=pra_high_ratio,
        n_ndd=n_ndd,
    )
    return build_kep_graph(
        instance,
        max_cycle_size=max_cycle_size,
        max_chain_length=max_chain_length,
    )
