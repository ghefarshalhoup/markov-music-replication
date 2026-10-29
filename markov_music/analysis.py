"""Turn a two-voice score into the training sequences the paper's models learn from.

Paper, "Music analysis" section:
- chord duration:   durations of the accompaniment after merging repeated chords
- chord progression: Roman numerals of those merged chords
- rhythm:           note values of the lead
- melodic arc:      hidden = (contour, scale degree) of each lead note, e.g. "+2";
                    observed = Roman numeral of the chord sounding when the note starts
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .musicxml_io import Event, Score, read_musicxml
from .theory import MAJOR_SCALE, Chord, classify_chord, degree_of


@dataclass
class ChordEvent:
    onset: int
    duration: int
    chord: Chord | None
    pitches: tuple[int, ...]

    @property
    def numeral(self) -> str:
        return (self.chord.numeral if self.chord else None) or "?"


@dataclass
class Piece:
    name: str
    style: str
    tempo: int
    n_bars: int
    lead: list[Event]
    chords: list[ChordEvent]


@dataclass
class Analysis:
    chord_durations: list[int]
    chord_numerals: list[str]
    rhythm: list[int]
    melody_hidden: list[str]
    melody_observed: list[str]
    chord_types: list[tuple[str, Chord]] = field(default_factory=list)
    first_pitch: int = 60
    notes_crossing_chords: int = 0


def _split_parts(score: Score) -> tuple[list[Event], list[Event]]:
    """Return (lead, accompaniment). Uses part names, else the part with more chords is the accompaniment."""
    names = {n.lower(): n for n in score.parts}
    if "lead" in names and "accompaniment" in names:
        return score.parts[names["lead"]], score.parts[names["accompaniment"]]
    by_polyphony = sorted(score.parts.values(), key=lambda evs: sum(len(e.pitches) > 1 for e in evs) / max(len(evs), 1))
    return by_polyphony[0], by_polyphony[-1]


def piece_from_score(score: Score, style: str) -> Piece:
    if score.key_mode != "major":
        raise NotImplementedError(f"{score.name}: only major keys are supported")
    tonic = (7 * score.key_fifths) % 12
    shift = -tonic if tonic <= 6 else 12 - tonic        # transpose to C by the smallest move
    lead, accompaniment = _split_parts(score)

    def move(e: Event) -> Event:
        return Event(e.onset, e.duration, tuple(p + shift for p in e.pitches))

    chords = [ChordEvent(e.onset, e.duration, classify_chord(e.pitches) if e.pitches else None, e.pitches)
              for e in map(move, accompaniment)]
    return Piece(score.name, style, score.tempo, score.n_bars, [move(e) for e in lead], chords)


def load_style(folder: str | Path, style: str | None = None) -> list[Piece]:
    folder = Path(folder)
    return [piece_from_score(read_musicxml(f), style or folder.name) for f in sorted(folder.glob("*.xml"))]


def merge_chords(chords: list[ChordEvent]) -> list[ChordEvent]:
    """Group chords that are the same and follow each other, summing their durations."""
    merged: list[ChordEvent] = []
    for c in chords:
        same = merged and c.chord is not None and merged[-1].chord == c.chord
        if same and merged[-1].onset + merged[-1].duration == c.onset:
            prev = merged[-1]
            merged[-1] = ChordEvent(prev.onset, prev.duration + c.duration, prev.chord, prev.pitches)
        else:
            merged.append(c)
    return merged


def chord_at(chords: list[ChordEvent], t: int) -> ChordEvent | None:
    return next((c for c in chords if c.onset <= t < c.onset + c.duration), None)


def encode_melody(pitches: list[int]) -> list[str]:
    """Contour (=, +, -) relative to the previous note, plus the scale degree."""
    symbols, prev = [], None
    for p in pitches:
        contour = "=" if prev is None or p == prev else ("+" if p > prev else "-")
        symbols.append(f"{contour}{degree_of(p)}")
        prev = p
    return symbols


def decode_melody(symbols: list[str], start_pitch: int) -> list[int]:
    """Inverse of encode_melody: move to the nearest note with the given degree in the given direction."""
    pitches, prev = [], None
    for s in symbols:
        contour, degree = s[0], int(s[1:])
        pc = MAJOR_SCALE[degree - 1]
        if prev is None:
            p = min((start_pitch - 6 + i for i in range(12)), key=lambda q: (q % 12 != pc, abs(q - start_pitch)))
        elif contour == "=":
            p = prev
        elif contour == "+":
            p = next(q for q in range(prev + 1, prev + 13) if q % 12 == pc)
        else:
            p = next(q for q in range(prev - 1, prev - 13, -1) if q % 12 == pc)
        pitches.append(p)
        prev = p
    return pitches


def analyse(piece: Piece) -> Analysis:
    merged = merge_chords(piece.chords)
    notes = [e for e in piece.lead if e.pitches]
    if len(notes) != len(piece.lead):
        raise NotImplementedError(f"{piece.name}: rests in the lead are not supported (the paper's data has none)")
    observed = []
    crossing = 0
    for n in notes:
        c = chord_at(merged, n.onset)
        observed.append(c.numeral if c else "?")
        crossing += bool(c and n.onset + n.duration > c.onset + c.duration)
    pitches = [n.pitches[-1] for n in notes]            # lead is one voice; take the top note if doubled
    return Analysis(
        chord_durations=[c.duration for c in merged],
        chord_numerals=[c.numeral for c in merged],
        rhythm=[n.duration for n in notes],
        melody_hidden=encode_melody(pitches),
        melody_observed=observed,
        chord_types=[(c.numeral, c.chord) for c in piece.chords if c.chord],
        first_pitch=pitches[0],
        notes_crossing_chords=crossing,
    )
