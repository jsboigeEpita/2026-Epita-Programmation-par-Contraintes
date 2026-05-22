"""Package melody - generation de melodies par programmation par contraintes."""

from melody.solver import (
    solve, solve_many, PROFILES,
    solve_with_fixed_notes, generate_variations,
)
from melody.export import (
    to_midi, to_text, to_abc, save_abc,
    plot_piano_roll,
)
from melody.music_theory import midi_to_name

__all__ = [
    "solve", "solve_many", "PROFILES",
    "solve_with_fixed_notes", "generate_variations",
    "to_midi", "to_text", "to_abc", "save_abc",
    "plot_piano_roll",
    "midi_to_name",
]