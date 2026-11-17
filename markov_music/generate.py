"""SuperWillow's generation pipeline (paper, "Music generation" section).

1. pick tempo from the style
2. chord durations that sum exactly to the requested length ("duration left" = 0)
3. a chord progression with exactly that many chords
4. a chord type for each numeral, from the chords stored by the accompaniment analysis
5. a lead rhythm whose notes fit inside the generated chord durations (and bar lines)
6. a melody sampled from the HMM given the chord under each note

Each step samples from its model, conditioned on the constraint. The steps don't
coordinate, so a step can find no valid output: the paper calls these "failed
composition attempts", and we report them per step.
"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .analysis import Analysis, ChordEvent, Piece, analyse, chord_at, decode_melody
from .hmm import Emission, sample_posterior
from .models import END, make_model
from .musicxml_io import Event
from .theory import BAR, Chord

sys.setrecursionlimit(10_000)


def sample_constrained(model, total: int, length_of, limit, rng: random.Random,
                       final: bool = True, memo: dict | None = None) -> tuple[list, list] | None:
    """Sample symbols whose lengths add up to exactly `total`.

    This is the paper's "duration left" construction: the state is extended with
    the time already used, and we only take steps that can still end exactly on
    `total` (in a final state). beta(state, t) is the probability of finishing
    correctly from there; sampling with weights p * beta gives an exact sample
    from the model conditioned on the constraint.

    length_of(symbol) -> its length; limit(t) -> latest time a symbol starting at t may end.
    memo can be shared between calls with the same model, length_of, limit and final, when
    what is allowed depends only on the time left. It saves recomputing beta for every piece.
    Returns (symbols, states they were sampled from) or None if no valid sequence exists.
    """
    memo = {} if memo is None else memo

    def options(state, t):
        lim = limit(t)
        for sym, p in model.dist(state).items():
            if sym != END and t + length_of(sym) <= lim:
                yield sym, p, model.next_state(state, sym), t + length_of(sym)

    def beta(state, t) -> float:
        key = (state, total - t)
        if key not in memo:
            if t == total:
                memo[key] = model.dist(state).get(END, 0.0) if final else 1.0
            else:
                memo[key] = sum(p * beta(nxt, t2) for _, p, nxt, t2 in options(state, t))
        return memo[key]

    state, t = model.initial_state(), 0
    if beta(state, 0) == 0:
        return None
    symbols, states = [], []
    while t < total:
        choices = [(sym, nxt, t2, p * beta(nxt, t2)) for sym, p, nxt, t2 in options(state, t)]
        sym, nxt, t2, _ = rng.choices(choices, weights=[c[3] for c in choices], k=1)[0]
        symbols.append(sym)
        states.append(state)
        state, t = nxt, t2
    return symbols, states


@dataclass
class StyleModel:
    style: str
    kind: str
    order: int
    chord_duration: object
    chord_progression: object
    rhythm: object
    melody: object
    emission: Emission
    chord_types: dict[str, Counter]
    tempos: list[int]
    first_pitches: list[int]


def train_style(pieces: list[Piece], kind: str, order: int, **psa_params) -> StyleModel:
    analyses: list[Analysis] = [analyse(p) for p in pieces]

    def fit(attr):
        return make_model(kind, order, **psa_params).fit([getattr(a, attr) for a in analyses])

    chord_types: dict[str, Counter] = defaultdict(Counter)
    for a in analyses:
        for numeral, chord in a.chord_types:
            chord_types[numeral][chord] += 1
    return StyleModel(
        style=pieces[0].style, kind=kind, order=order,
        chord_duration=fit("chord_durations"),
        chord_progression=fit("chord_numerals"),
        rhythm=fit("rhythm"),
        melody=fit("melody_hidden"),
        emission=Emission().fit([a.melody_hidden for a in analyses], [a.melody_observed for a in analyses]),
        chord_types=dict(chord_types),
        tempos=[p.tempo for p in pieces],
        first_pitches=[a.first_pitch for a in analyses],
    )


@dataclass
class Result:
    piece: Piece | None
    failed_step: str | None
    memory: dict[str, list[int]] = field(default_factory=dict)   # step -> memory length per choice


def generate(sm: StyleModel, n_bars: int, rng: random.Random, name: str = "generated") -> Result:
    total = n_bars * BAR
    memory: dict[str, list[int]] = {}

    def used(step, model, states):
        memory[step] = [model.memory(s) for s in states]

    out = sample_constrained(sm.chord_duration, total, lambda d: d, lambda t: total, rng)
    if out is None:
        return Result(None, "chord durations", memory)
    durations, states = out
    used("chord durations", sm.chord_duration, states)

    k = len(durations)
    out = sample_constrained(sm.chord_progression, k, lambda _: 1, lambda t: k, rng)
    if out is None:
        return Result(None, "chord progression", memory)
    numerals, states = out
    used("chord progression", sm.chord_progression, states)

    chords, onset = [], 0
    for numeral, dur in zip(numerals, durations):
        types = sm.chord_types.get(numeral)
        if not types:
            return Result(None, "chord type", memory)
        chord: Chord = rng.choices(list(types), weights=list(types.values()), k=1)[0]
        chords.append(ChordEvent(onset, dur, chord, tuple(chord.voicing())))
        onset += dur

    boundaries = sorted({c.onset + c.duration for c in chords} | set(range(BAR, total + 1, BAR)))

    def next_boundary(t):
        return next(b for b in boundaries if b > t)

    out = sample_constrained(sm.rhythm, total, lambda d: d, next_boundary, rng)
    if out is None:
        return Result(None, "rhythm", memory)
    rhythm, states = out
    used("rhythm", sm.rhythm, states)

    onsets = [sum(rhythm[:i]) for i in range(len(rhythm))]
    observed = [chord_at(chords, t).numeral for t in onsets]
    out = sample_posterior(sm.melody, sm.emission, observed, rng)
    if out is None:
        return Result(None, "melody", memory)
    hidden, states = out
    used("melody", sm.melody, states)

    pitches = decode_melody(hidden, rng.choice(sm.first_pitches))
    lead = [Event(t, d, (p,)) for t, d, p in zip(onsets, rhythm, pitches)]
    piece = Piece(name, sm.style, rng.choice(sm.tempos), n_bars, lead, chords)
    return Result(piece, None, memory)
