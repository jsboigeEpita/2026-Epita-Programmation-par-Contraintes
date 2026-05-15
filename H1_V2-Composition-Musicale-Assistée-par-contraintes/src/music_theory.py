"""
music_theory.py
----------------
Constantes musicales et petits helpers utilises par le solveur.

L'idee : isoler ici tout ce qui est "savoir musical" pour que le solveur
(solver.py) ne contienne que de la logique CP. Comme ca, on peut changer
de gamme ou de tonalite sans toucher au modele CP-SAT.
"""

# --- Hauteurs MIDI ---------------------------------------------------------
# En MIDI, chaque note est un entier de 0 a 127.
# Do central (C4) = 60. Chaque +1 = un demi-ton.
# Une octave = 12 demi-tons.
#
# Le "pitch class" est pitch % 12 :
#   0 = Do (C), 1 = Do# (C#), 2 = Re (D), ...,  11 = Si (B)
#
# Une gamme est un ensemble de 7 pitch classes parmi les 12.

# Gammes les plus courantes.
# Chaque entree contient :
#   - 'tonic' : pitch class de la tonique (la note "centre" de la gamme)
#   - 'pcs'   : liste des 7 pitch classes appartenant a la gamme
#
# Exemple : La mineur naturel a pour tonique La (pc=9) et les notes
# La Si Do Re Mi Fa Sol -> pcs = [9, 11, 0, 2, 4, 5, 7]
# Les pcs sont listees DANS L'ORDRE des degres (I, II, III, IV, V, VI, VII)
# ce qui simplifie l'acces a la dominante (pcs[4]) et a la sensible (pcs[6]).
SCALES = {
    "C_major": {
        "tonic": 0,
        "pcs":   [0, 2, 4, 5, 7, 9, 11],   # Do Re Mi Fa Sol La Si
    },
    "G_major": {
        "tonic": 7,
        "pcs":   [7, 9, 11, 0, 2, 4, 6],   # Sol La Si Do Re Mi Fa#
    },
    "A_minor": {
        "tonic": 9,
        "pcs":   [9, 11, 0, 2, 4, 5, 7],   # La Si Do Re Mi Fa Sol
    },
}

# Noms des notes pour l'affichage
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi_pitch: int) -> str:
    """
    Convertit un numero MIDI (ex 60) en nom de note (ex 'C4').
    Utile pour afficher une melodie de facon lisible.
    """
    octave = midi_pitch // 12 - 1   # C4 = 60 -> octave 4
    name = NOTE_NAMES[midi_pitch % 12]
    return f"{name}{octave}"


def scale_pitches(scale_name: str, low: int = 55, high: int = 79) -> list[int]:
    """
    Retourne la liste de toutes les hauteurs MIDI appartenant a la gamme,
    dans la plage [low, high].

    Par defaut, la plage va de 55 (Sol3) a 79 (Sol5),
    ce qui couvre confortablement une tessiture de chanteur moyen.

    Cette liste sera le domaine de chaque variable pitch[t] du CSP.
    En reduisant le domaine ici (au lieu de poser "pitch % 12 in scale" comme
    contrainte), on aide le solveur a explorer un espace bien plus petit.
    """
    scale_pcs = SCALES[scale_name]["pcs"]
    return [p for p in range(low, high + 1) if p % 12 in scale_pcs]


# --- Degres et cadences ----------------------------------------------------
# En harmonie tonale, chaque degre de la gamme a un role :
#   I   (tonique)   : repos, fin de phrase
#   V   (dominante) : tension, appelle la tonique
#   VII (sensible)  : un demi-ton sous la tonique, doit "monter" vers elle
#
# Une "cadence parfaite" termine par V -> I.
# Une "cadence en sensible" termine par VII -> I.
# Les deux sonnent "finies".

def tonic_pitch_classes(scale_name: str) -> list[int]:
    """Pitch class de la tonique (premier degre)."""
    return [SCALES[scale_name]["tonic"]]


def dominant_or_leading_tone_pcs(scale_name: str) -> list[int]:
    """
    Pitch classes admises pour l'avant-derniere note :
    la dominante (5e degre) ou la sensible (7e degre).
    """
    pcs = SCALES[scale_name]["pcs"]
    return [pcs[4], pcs[6]]   # indices 4 et 6 = degres V et VII