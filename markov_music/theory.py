"""Music-theory helpers: pitches, scale degrees, chord classification, note values.

Conventions used throughout the package:
- pitches are MIDI numbers (C4 = 60);
- time is measured in sixteenth notes (a quarter note = 4, a 4/4 bar = 16);
- all music is in C major after extraction (the paper transposes to C).
"""
from __future__ import annotations

from dataclasses import dataclass

STEP_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
PC_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]  # pitch classes of C major, degree 1..7
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII"]
BAR = 16  # sixteenths per 4/4 bar


def midi_pitch(step: str, alter: int, octave: int) -> int:
    return 12 * (octave + 1) + STEP_PC[step] + alter


def pitch_name(midi: int) -> str:
    return f"{PC_NAMES[midi % 12]}{midi // 12 - 1}"


def degree_of(midi: int) -> int | None:
    """Scale degree 1..7 of a pitch in C major, or None for a chromatic note."""
    pc = midi % 12
    return MAJOR_SCALE.index(pc) + 1 if pc in MAJOR_SCALE else None


# --- chords ----------------------------------------------------------------

# Interval sets (semitones above the root). Order matters only to break ties
# when a pitch set fits several roots and none of them is the bass note.
CHORD_TEMPLATES: list[tuple[str, frozenset[int]]] = [
    ("maj", frozenset({0, 4, 7})),
    ("min", frozenset({0, 3, 7})),
    ("dim", frozenset({0, 3, 6})),
    ("aug", frozenset({0, 4, 8})),
    ("7", frozenset({0, 4, 7, 10})),
    ("maj7", frozenset({0, 4, 7, 11})),
    ("min7", frozenset({0, 3, 7, 10})),
    ("m7b5", frozenset({0, 3, 6, 10})),
    ("add9", frozenset({0, 2, 4, 7})),
    ("add4", frozenset({0, 4, 5, 7})),
    ("sus2", frozenset({0, 2, 7})),
    ("sus4", frozenset({0, 5, 7})),
    ("5", frozenset({0, 7})),          # power chord
    ("M3", frozenset({0, 4})),         # major-third dyad
    ("m3", frozenset({0, 3})),         # minor-third dyad
    ("1", frozenset({0})),             # single note
]
TEMPLATE_BY_NAME = dict(CHORD_TEMPLATES)


@dataclass(frozen=True)
class Chord:
    root_pc: int
    quality: str

    @property
    def numeral(self) -> str | None:
        """Roman numeral = position of the root in the C major scale (the paper ignores quality)."""
        return ROMAN[MAJOR_SCALE.index(self.root_pc)] if self.root_pc in MAJOR_SCALE else None

    def voicing(self, octave: int = 4) -> list[int]:
        """Chord tones placed in one octave, as in SuperWillow's published outputs."""
        base = 12 * (octave + 1)
        return sorted(base + (self.root_pc + i) % 12 for i in TEMPLATE_BY_NAME[self.quality])

    def __str__(self) -> str:
        return f"{PC_NAMES[self.root_pc]}{'' if self.quality == 'maj' else ':' + self.quality}"


def classify_chord(pitches: list[int] | tuple[int, ...]) -> Chord | None:
    """Find root and type of a block chord from its pitch classes.

    Inversions are handled: E4+A4+C5 is A minor. When several roots fit
    (e.g. Dsus2 = Asus4), the bass note wins. Returns None for unknown chords.
    """
    pcs = {p % 12 for p in pitches}
    bass = min(pitches) % 12
    matches = [
        (rank, root, name)
        for rank, (name, intervals) in enumerate(CHORD_TEMPLATES)
        for root in pcs
        if {(pc - root) % 12 for pc in pcs} == intervals
    ]
    if not matches:
        return None
    matches.sort(key=lambda m: (m[1] != bass, m[0]))
    return Chord(matches[0][1], matches[0][2])


# --- note values -----------------------------------------------------------

# Durations in sixteenths that can be written as a single (possibly dotted) note.
NOTE_TYPES = {16: ("whole", 0), 12: ("half", 1), 8: ("half", 0), 6: ("quarter", 1),
              4: ("quarter", 0), 3: ("eighth", 1), 2: ("eighth", 0), 1: ("16th", 0)}


def split_writable(duration: int) -> list[int]:
    """Break a duration into note values that can each be written without ties."""
    parts, left = [], duration
    for value in sorted(NOTE_TYPES, reverse=True):
        while left >= value:
            parts.append(value)
            left -= value
    return parts
