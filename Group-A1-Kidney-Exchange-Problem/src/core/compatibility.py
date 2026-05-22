
from src.core.graph import Donor, Patient


BLOOD_TYPE_COMPATIBILITY = {
    'O':  ['O', 'A', 'B', 'AB'],
    'A':  ['A', 'AB'],
    'B':  ['B', 'AB'],
    'AB': ['AB'],
}

class CompatibilityChecker:
    def check(self, donor: Donor, patient: Patient) -> float:
        """
        Retourne un poids > 0 si compatible, 0 sinon.
        Le poids reflète la qualité de la compatibilité.
        """
        # Niveau 1 : groupe sanguin (éliminatoire)
        if patient.blood_type not in BLOOD_TYPE_COMPATIBILITY[donor.blood_type]:
            return 0.0

        # Niveau 2 : anticorps HLA (éliminatoire)
        for antibody in patient.hla_antibodies:
            if antibody in donor.hla_antigens:
                return 0.0

        # Score de compatibilité HLA
        hla_matches = sum(
            1 for ag in donor.hla_antigens
            if ag not in patient.hla_antibodies
        )

        # Pondération : priorité aux patients très sensibilisés (PRA élevé)
        priority_bonus = 1.0 + patient.pra

        return max(1.0, hla_matches * priority_bonus)