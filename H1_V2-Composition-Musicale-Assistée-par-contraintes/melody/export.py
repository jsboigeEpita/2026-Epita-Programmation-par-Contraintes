"""
export.py
----------
Export d'une melodie generee vers :
  - un fichier MIDI ecoutable (avec midiutil)
  - une figure matplotlib "piano roll" (pour visualiser)
  - une chaine au format ABC notation (pour rendre une partition)

On garde toutes les durees a la noire (4 ticks MIDI = 1 noire si
on fixe les divisions a 4). C'est volontairement simple : on s'est
concentre sur les HAUTEURS, pas le rythme.
"""

from midiutil import MIDIFile
from melody.music_theory import midi_to_name, SCALES


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


# --- Export ABC notation ---------------------------------------------------
#
# ABC notation est un format TEXTE standard pour ecrire des partitions.
# Tres lisible, tres compact. Exemple :
#
#   X:1
#   T:Ma melodie
#   M:4/4
#   L:1/4
#   K:C
#   C D E F | G A B c | c B A G | F E D C |
#
# Pour le visualiser comme une vraie partition, il suffit de coller le
# texte sur https://www.abcjs.net/ ou https://abcjs.net/abcjs-editor.html
# (ils transforment le texte ABC en partition graphique instantanement).
#
# Regles ABC pour les hauteurs :
#   C, D, E, F, G, A, B  = notes de l'octave 4 (C4..B4 en MIDI)
#   c, d, e, f, g, a, b  = notes de l'octave 5 (une octave au-dessus)
#   ',' apres = octave plus basse (ex: C, = C3)
#   "'" apres = octave plus haute (ex: c' = C6)
#
# Notre approche : on convertit chaque hauteur MIDI en son code ABC.

def to_abc(melody: list[int],
           title: str = "Generated melody",
           scale_name: str = "C_major",
           tempo: int = 100) -> str:
    """
    Convertit une melodie en notation ABC, prete a etre rendue comme une
    vraie partition sur https://www.abcjs.net/.

    Parametres
    ----------
    melody : list[int]   - hauteurs MIDI (une par noire)
    title : str          - titre affiche en haut de la partition
    scale_name : str     - gamme (pour mettre le bon "K:" en ABC)
    tempo : int          - tempo en BPM

    Retourne
    --------
    str : la partition au format ABC (a copier-coller sur abcjs.net)
    """
    # --- En-tete ABC (metadata) -------------------------------------------
    # X = identifiant unique
    # T = titre
    # M = mesure (4/4)
    # L = duree de note par defaut (1/4 = noire)
    # Q = tempo
    # K = tonalite (clef de gamme)
    abc_key = _abc_key_signature(scale_name)
    lines = [
        "X:1",
        f"T:{title}",
        "M:4/4",
        "L:1/4",
        f"Q:1/4={tempo}",
        f"K:{abc_key}",
    ]

    # --- Corps : les notes ------------------------------------------------
    # On groupe les notes par 4 (= une mesure en 4/4), separees par '|'
    abc_notes = [_midi_to_abc_note(p) for p in melody]
    bars = []
    for i in range(0, len(abc_notes), 4):
        bars.append(" ".join(abc_notes[i:i + 4]))
    body = " | ".join(bars) + " |"
    lines.append(body)

    return "\n".join(lines)


def _midi_to_abc_note(midi_pitch: int) -> str:
    """
    Convertit une hauteur MIDI en code ABC.

    Octaves de reference en ABC :
      octave 4 (MIDI 60-71) = majuscules sans suffixe : C D E F G A B
      octave 5 (MIDI 72-83) = minuscules sans suffixe : c d e f g a b
      octave 3 (MIDI 48-59) = majuscules avec ',' : C, D, E, ...
      octave 6 (MIDI 84-95) = minuscules avec "'" : c' d' e' ...

    Pour les diezes : on prefixe par '^' (ex: ^F = Fa#)
    """
    # On utilise les noms MIDI standards (C, C#, D, ..., B)
    note_names_natural = ["C", None, "D", None, "E", "F", None, "G", None, "A", None, "B"]
    note_names_sharp =   [None, "^C", None, "^D", None, None, "^F", None, "^G", None, "^A", None]

    pc = midi_pitch % 12
    octave = midi_pitch // 12 - 1   # MIDI 60 -> octave 4

    # Recuperer le nom de base (avec ou sans diese)
    name = note_names_natural[pc] or note_names_sharp[pc]

    # Adapter casse + suffixe selon l'octave ABC
    if octave == 4:
        return name                          # 'C', 'D', '^F', ...
    elif octave == 5:
        return name.lower()                  # 'c', 'd', '^f', ...
    elif octave < 4:
        # 1 virgule par octave en dessous de 4
        return name + "," * (4 - octave)     # 'C,' pour octave 3, 'C,,' pour octave 2
    else:  # octave > 5
        # 1 apostrophe par octave au-dessus de 5
        return name.lower() + "'" * (octave - 5)


def _abc_key_signature(scale_name: str) -> str:
    """
    Convertit notre nom de gamme interne en signature ABC.

    ABC utilise la convention "C" (majeur) ou "Am" (mineur).
    """
    mapping = {
        "C_major": "C",
        "G_major": "G",
        "A_minor": "Am",
    }
    return mapping.get(scale_name, "C")


def save_abc(melody: list[int], path: str, **kwargs) -> None:
    """Sauve la melodie en fichier .abc (texte) pour partage."""
    content = to_abc(melody, **kwargs)
    with open(path, "w") as f:
        f.write(content)


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