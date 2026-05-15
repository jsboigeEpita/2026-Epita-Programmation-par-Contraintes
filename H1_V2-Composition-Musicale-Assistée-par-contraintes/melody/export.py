"""
export.py
----------
Export d'une melodie generee vers :
  - un fichier MIDI ecoutable (avec midiutil)
  - une figure matplotlib "piano roll" (pour visualiser)

On garde toutes les durees a la noire (4 ticks MIDI = 1 noire si
on fixe les divisions a 4). C'est volontairement simple : on s'est
concentre sur les HAUTEURS, pas le rythme.
"""

from midiutil import MIDIFile
from melody.music_theory import midi_to_name


# --- Export MIDI -----------------------------------------------------------

def to_midi(melody: list[int], path: str, tempo: int = 100) -> None:
    """
    Sauve une melodie en fichier MIDI.

    Parametres
    ----------
    melody : list[int]   - liste de hauteurs MIDI (une par noire)
    path : str           - chemin du fichier .mid a creer
    tempo : int          - tempo en BPM (battements par minute)
    """
    midi = MIDIFile(numTracks=1)   # une seule piste (melodie monodique)
    track = 0
    channel = 0
    volume = 100                    # volume MIDI (0-127)

    midi.addTempo(track, time=0, tempo=tempo)

    # On place les notes les unes apres les autres, chacune dure 1 noire
    for i, pitch in enumerate(melody):
        midi.addNote(
            track=track,
            channel=channel,
            pitch=pitch,
            time=i,        # temps de debut en noires
            duration=1,    # duree en noires
            volume=volume,
        )

    with open(path, "wb") as f:
        midi.writeFile(f)


# --- Affichage texte -------------------------------------------------------

def to_text(melody: list[int]) -> str:
    """
    Retourne une representation lisible de la melodie.
    Exemple : 'C4 E4 G4 C5 B4 G4 E4 C4'
    """
    return " ".join(midi_to_name(p) for p in melody)


# --- Piano roll matplotlib -------------------------------------------------

def plot_piano_roll(melody: list[int], title: str = "Melody", ax=None):
    """
    Trace un "piano roll" : chaque note est un rectangle horizontal,
    x = temps, y = hauteur.

    Si ax est fourni, dessine dedans (utile pour les sous-figures dans
    le notebook). Sinon, cree une figure standalone.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))

    # Une barre par note
    for i, pitch in enumerate(melody):
        ax.barh(pitch, width=1, left=i, height=0.8,
                color="steelblue", edgecolor="black")

    # Habillage
    ax.set_xlabel("Temps (en noires)")
    ax.set_ylabel("Hauteur MIDI")
    ax.set_title(title)
    ax.set_xlim(0, len(melody))

    # Une grille horizontale + labels des octaves (C3, C4, C5, ...)
    pmin, pmax = min(melody) - 2, max(melody) + 2
    ax.set_ylim(pmin, pmax)
    for p in range(pmin, pmax + 1):
        if p % 12 == 0:    # C de chaque octave
            ax.axhline(p, color="gray", linewidth=0.3, linestyle="--")
            ax.text(-0.3, p, midi_to_name(p), ha="right", va="center", fontsize=8)

    return ax