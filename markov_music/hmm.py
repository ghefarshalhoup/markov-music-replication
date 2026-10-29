"""Hidden Markov model for the melodic arc, on top of any sequence model from models.py.

The hidden chain is a higher-order MC or a PSA over melody symbols (e.g. "+2").
Each hidden state emits the chord numeral under the note; as in the paper, the
emission distribution depends only on the last symbol of the state label.

Generation is "noisy channel decoding": the chords are given, and a melody is
*sampled* from P(melody | chords), not the most probable melody. We do this exactly
with forward filtering, backward sampling.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

from .models import END


class Emission:
    def __init__(self):
        self.table: dict[str, dict[str, float]] = {}

    def fit(self, hidden: list[list[str]], observed: list[list[str]]) -> "Emission":
        counts: dict[str, Counter] = defaultdict(Counter)
        for hs, os in zip(hidden, observed):
            for h, o in zip(hs, os):
                counts[h][o] += 1
        self.table = {h: {o: n / sum(c.values()) for o, n in c.items()} for h, c in counts.items()}
        return self

    def prob(self, hidden: str, observed: str) -> float:
        return self.table.get(hidden, {}).get(observed, 0.0)


def sample_posterior(model, emission: Emission, observations: list[str], rng: random.Random,
                     final: bool = True) -> tuple[list[str], list] | None:
    """Sample hidden symbols given observations. Returns (symbols, states used) or None if impossible."""
    alpha = {model.initial_state(): 1.0}
    backpointers = []
    for obs in observations:
        new: dict = defaultdict(float)
        back: dict = defaultdict(list)
        for state, a in alpha.items():
            for sym, p in model.dist(state).items():
                if sym == END:
                    continue
                w = a * p * emission.prob(sym, obs)
                if w > 0:
                    nxt = model.next_state(state, sym)
                    new[nxt] += w
                    back[nxt].append((state, sym, w))
        if not new:
            return None
        z = sum(new.values())                       # rescale to avoid underflow
        alpha = {s: v / z for s, v in new.items()}
        backpointers.append(back)

    ends = {s: a * (model.dist(s).get(END, 0.0) if final else 1.0) for s, a in alpha.items()}
    if sum(ends.values()) == 0:
        return None
    state = _pick(list(ends), list(ends.values()), rng)
    symbols, states = [], []
    for back in reversed(backpointers):
        prev, sym, _ = _pick(back[state], [w for *_, w in back[state]], rng)
        symbols.append(sym)
        states.append(prev)
        state = prev
    return symbols[::-1], states[::-1]


def _pick(items, weights, rng: random.Random):
    return rng.choices(items, weights=weights, k=1)[0]
