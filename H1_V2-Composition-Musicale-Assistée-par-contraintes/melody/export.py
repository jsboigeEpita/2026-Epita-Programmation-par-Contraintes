from midiutil import MIDIFile
from melody.music_theory import midi_to_name, SCALES

def to_midi(melody: list[int], path: str, tempo: int=100) -> None:
    midi = MIDIFile(numTracks=1)
    track = 0
    channel = 0
    volume = 100
    midi.addTempo(track, time=0, tempo=tempo)
    for i, pitch in enumerate(melody):
        midi.addNote(track=track, channel=channel, pitch=pitch, time=i, duration=1, volume=volume)
    with open(path, 'wb') as f:
        midi.writeFile(f)

def to_text(melody: list[int]) -> str:
    return ' '.join((midi_to_name(p) for p in melody))

def to_abc(melody: list[int], title: str='Generated melody', scale_name: str='C_major', tempo: int=100) -> str:
    abc_key = _abc_key_signature(scale_name)
    lines = ['X:1', f'T:{title}', 'M:4/4', 'L:1/4', f'Q:1/4={tempo}', f'K:{abc_key}']
    abc_notes = [_midi_to_abc_note(p) for p in melody]
    bars = []
    for i in range(0, len(abc_notes), 4):
        bars.append(' '.join(abc_notes[i:i + 4]))
    body = ' | '.join(bars) + ' |'
    lines.append(body)
    return '\n'.join(lines)

def _midi_to_abc_note(midi_pitch: int) -> str:
    note_names_natural = ['C', None, 'D', None, 'E', 'F', None, 'G', None, 'A', None, 'B']
    note_names_sharp = [None, '^C', None, '^D', None, None, '^F', None, '^G', None, '^A', None]
    pc = midi_pitch % 12
    octave = midi_pitch // 12 - 1
    name = note_names_natural[pc] or note_names_sharp[pc]
    if octave == 4:
        return name
    elif octave == 5:
        return name.lower()
    elif octave < 4:
        return name + ',' * (4 - octave)
    else:
        return name.lower() + "'" * (octave - 5)

def _abc_key_signature(scale_name: str) -> str:
    mapping = {'C_major': 'C', 'G_major': 'G', 'A_minor': 'Am'}
    return mapping.get(scale_name, 'C')

def save_abc(melody: list[int], path: str, **kwargs) -> None:
    content = to_abc(melody, **kwargs)
    with open(path, 'w') as f:
        f.write(content)

def plot_piano_roll(melody: list[int], title: str='Melody', ax=None):
    import matplotlib.pyplot as plt
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 4))
    for i, pitch in enumerate(melody):
        ax.barh(pitch, width=1, left=i, height=0.8, color='steelblue', edgecolor='black')
    ax.set_xlabel('Temps (en noires)')
    ax.set_ylabel('Hauteur MIDI')
    ax.set_title(title)
    ax.set_xlim(0, len(melody))
    pmin, pmax = (min(melody) - 2, max(melody) + 2)
    ax.set_ylim(pmin, pmax)
    for p in range(pmin, pmax + 1):
        if p % 12 == 0:
            ax.axhline(p, color='gray', linewidth=0.3, linestyle='--')
            ax.text(-0.3, p, midi_to_name(p), ha='right', va='center', fontsize=8)
    return ax