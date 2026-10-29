"""Measurements used to check the replication against the paper."""
from __future__ import annotations

from collections import Counter
from statistics import mean

from .analysis import Piece, analyse, merge_chords
from .theory import BAR


def note_tokens(piece: Piece) -> list[tuple]:
    """Lead as (interval from previous note, duration): independent of octave, so copies are found
    even when a generated melody starts in a different octave than the training piece."""
    pitches = [e.pitches[-1] for e in piece.lead]
    return [(None if i == 0 else pitches[i] - pitches[i - 1], e.duration) for i, e in enumerate(piece.lead)]


def longest_common_run(a: list, b: list) -> int:
    """Length of the longest contiguous run shared by a and b."""
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def copy_stats(piece: Piece, training: list[Piece], n: int = 4) -> dict:
    """How much of the lead is copied from the training pieces (paper: open question)."""
    gen = note_tokens(piece)[1:]                 # first note has no interval
    train = [note_tokens(p)[1:] for p in training]
    longest = max(longest_common_run(gen, t) for t in train)
    train_grams = {tuple(t[i:i + n]) for t in train for i in range(len(t) - n + 1)}
    grams = [tuple(gen[i:i + n]) for i in range(len(gen) - n + 1)]
    return {
        "longest_copied_run": longest,
        "copied_fraction": longest / len(gen),
        f"{n}gram_overlap": sum(g in train_grams for g in grams) / len(grams),
        "verbatim": longest == len(gen),
    }


def features(pieces: list[Piece]) -> dict:
    """Descriptive statistics of a set of pieces, for comparing ours, the paper's and the training data."""
    durations, numerals, intervals, chord_durs = Counter(), Counter(), Counter(), Counter()
    notes_per_bar, ends_on_tonic, ends_on_I, spans = [], [], [], []
    for p in pieces:
        a = analyse(p)
        durations.update(a.rhythm)
        numerals.update(a.chord_numerals)
        chord_durs.update(a.chord_durations)
        pitches = [e.pitches[-1] for e in p.lead]
        intervals.update(min(abs(y - x), 13) for x, y in zip(pitches, pitches[1:]))
        notes_per_bar.append(len(p.lead) / (sum(a.rhythm) / BAR))
        ends_on_tonic.append(pitches[-1] % 12 == 0)
        ends_on_I.append(merge_chords(p.chords)[-1].numeral == "I")
        spans.append(max(pitches) - min(pitches))
    return {
        "n_pieces": len(pieces),
        "notes_per_bar": mean(notes_per_bar),
        "ends_on_tonic": mean(ends_on_tonic),
        "ends_on_chord_I": mean(ends_on_I),
        "pitch_span": mean(spans),
        "mean_abs_interval": sum(k * v for k, v in intervals.items()) / sum(intervals.values()),
        "leaps_over_octave": intervals[13] / sum(intervals.values()),
        "durations": _share(durations),
        "numerals": _share(numerals),
        "chord_durations": _share(chord_durs),
    }


def _share(c: Counter) -> dict:
    total = sum(c.values())
    return {str(k): v / total for k, v in sorted(c.items(), key=lambda kv: -kv[1])}


def tv_distance(p: dict, q: dict) -> float:
    """Total variation distance between two distributions: 0 = identical, 1 = disjoint."""
    return 0.5 * sum(abs(p.get(k, 0) - q.get(k, 0)) for k in set(p) | set(q))
