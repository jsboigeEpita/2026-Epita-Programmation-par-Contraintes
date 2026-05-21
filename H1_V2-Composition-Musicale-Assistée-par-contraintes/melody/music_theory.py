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

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi_pitch: int) -> str:
    octave = midi_pitch // 12 - 1
    name = NOTE_NAMES[midi_pitch % 12]
    return f"{name}{octave}"


def scale_pitches(scale_name: str, low: int = 55, high: int = 79) -> list[int]:
    scale_pcs = SCALES[scale_name]["pcs"]
    return [p for p in range(low, high + 1) if p % 12 in scale_pcs]


def tonic_pitch_classes(scale_name: str) -> list[int]:
    return [SCALES[scale_name]["tonic"]]


def dominant_or_leading_tone_pcs(scale_name: str) -> list[int]:
    pcs = SCALES[scale_name]["pcs"]
    return [pcs[4], pcs[6]]   # indices 4 et 6 = degres V et VII