"""The POP909 baseline: three separate n-th order chains, and how they are measured.

Each chain (note and rest lengths, pitches, loudness levels) looks only at its own last n values.
A piece is generated rhythm first, as in the paper: lengths that fill the bars exactly, then as
many pitches and loudness levels as the rhythm has notes. Generation uses raw counts; smoothing
is only used to score held-out songs.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from statistics import mean

import numpy as np

from .evaluate import tv_distance
from .generate import sample_constrained
from .models import START, HigherOrderMC
from .pop909 import WINDOW_BARS, Melody, token_length
from .theory import BAR

CHAINS = ("length", "pitch", "level")
STATISTICS = ("pitch", "pitch class", "pitch step", "length", "length pair", "loudness", "loudness step")
VIEWS = ("melody", "pitch step", "length", "loudness")


# --- generation ------------------------------------------------------------

@dataclass
class Chains:
    models: dict[str, HigherOrderMC]
    tempos: list[int]
    memos: dict[str, dict] = field(default_factory=lambda: {c: {} for c in CHAINS})


def fit_chains(train: list[Melody], orders: dict[str, int]) -> Chains:
    """No final states: pieces stop where the bars are full, not where a song ended."""
    models = {c: HigherOrderMC(orders[c]).fit([m.sequence(c) for m in train], final=False) for c in CHAINS}
    return Chains(models, [m.tempo for m in train])


def next_bar_line(t: int) -> int:
    return (t // BAR + 1) * BAR


def generate_melody(chains: Chains, rng: random.Random, name: str, n_bars: int = 8) -> tuple[Melody | None, str | None]:
    """A piece, or None and the chain that found no valid output."""
    out = sample_constrained(chains.models["length"], n_bars * BAR, token_length, next_bar_line, rng,
                             final=False, memo=chains.memos["length"])
    if out is None:
        return None, "length"
    tokens = out[0]
    n_notes = sum(t[0] == "N" for t in tokens)
    if n_notes == 0:                     # all rests: only possible without memory
        return None, "length"
    parts = {}
    for chain in ("pitch", "level"):
        out = sample_constrained(chains.models[chain], n_notes, lambda _: 1, lambda t: n_notes, rng,
                                 final=False, memo=chains.memos[chain])
        if out is None:
            return None, chain
        parts[chain] = out[0]
    return Melody(name, tokens, parts["pitch"], parts["level"], rng.choice(chains.tempos)), None


# --- predicting held-out songs ---------------------------------------------

class WittenBell:
    """P(symbol | last k symbols), backing off from no memory up to memory k (Witten & Bell 1991).

    Each context adds to its counts one extra count per distinct next symbol, shared out by the
    shorter context. With no memory the shorter context is a uniform guess over vocab_size symbols.
    """

    def __init__(self, sequences: list[list], max_order: int, vocab_size: int):
        self.max_order = max_order
        self.floor = 1 / vocab_size
        self.counts: dict[tuple, Counter] = defaultdict(Counter)
        for seq in sequences:
            padded = [START] * max_order + list(seq)
            for i in range(max_order, len(padded)):
                for k in range(max_order + 1):
                    self.counts[tuple(padded[i - k:i])][padded[i]] += 1

    def _weight(self, seen: Counter) -> float:
        return len(seen)

    def probs(self, context: list, symbol) -> list[float]:
        """P(symbol | context) with memory 0, 1, ..., max_order."""
        p, out = self.floor, []
        for k in range(self.max_order + 1):
            seen = self.counts.get(tuple(context[len(context) - k:]))
            if seen:
                weight = self._weight(seen)
                p = (seen[symbol] + weight * p) / (sum(seen.values()) + weight)
            out.append(p)
        return out

    def bits(self, sequence: list) -> np.ndarray:
        """Total bits to encode the sequence, with memory 0, 1, ..., max_order."""
        padded = [START] * self.max_order + list(sequence)
        total = np.zeros(self.max_order + 1)
        for i in range(self.max_order, len(padded)):
            total -= np.log2(self.probs(padded[i - self.max_order:i], padded[i]))
        return total


class FixedPrior(WittenBell):
    """The same backoff, trusting the shorter context with a fixed weight. Only used to see how much
    the choice of n depends on the smoothing."""

    def __init__(self, sequences: list[list], max_order: int, vocab_size: int, weight: float):
        super().__init__(sequences, max_order, vocab_size)
        self.weight = weight

    def _weight(self, seen: Counter) -> float:
        return self.weight


# --- statistics of a set of melodies ---------------------------------------

def steps(values: list[int]) -> list[int]:
    return [b - a for a, b in zip(values, values[1:])]


def distributions(melodies: list[Melody]) -> dict[str, dict]:
    counts = {s: Counter() for s in STATISTICS}
    for m in melodies:
        counts["pitch"].update(m.pitches)
        counts["pitch class"].update(p % 12 for p in m.pitches)
        counts["pitch step"].update(steps(m.pitches))
        counts["length"].update(m.tokens)
        counts["length pair"].update(zip(m.tokens, m.tokens[1:]))
        counts["loudness"].update(m.levels)
        counts["loudness step"].update(steps(m.levels))
    return {s: {str(k): v / sum(c.values()) for k, v in c.items()} for s, c in counts.items()}


def entropy(distribution: dict) -> float:
    p = np.array(list(distribution.values()))
    return float(-(p * np.log2(p)).sum())


def group_tv(melodies: list[Melody], reference: dict[str, dict], rng: random.Random,
             size: int, repeats: int) -> dict[str, dict]:
    """Distance of random groups of melodies from the reference, per statistic. Groups are sized to
    hold about as many notes as the reference, so sampling noise is comparable between sets."""
    distances = defaultdict(list)
    for _ in range(repeats):
        group = distributions(rng.sample(melodies, min(size, len(melodies))))
        for s in STATISTICS:
            distances[s].append(tv_distance(group[s], reference[s]))
    return {s: {"mean": mean(d), "p5": float(np.percentile(d, 5)), "p95": float(np.percentile(d, 95))}
            for s, d in distances.items()}


def piece_features(m: Melody) -> dict[str, float]:
    return {"notes": len(m.pitches),
            "distinct pitches": len(set(m.pitches)),
            "pitch range": max(m.pitches) - min(m.pitches),
            "mean step size": mean(abs(s) for s in steps(m.pitches)) if len(m.pitches) > 1 else 0.0,
            "rests": sum(t[0] == "R" for t in m.tokens),
            "silent sixteenths": WINDOW_BARS * BAR - sum(token_length(t) for t in m.tokens if t[0] == "N"),
            "loudness range": max(m.levels) - min(m.levels),
            "mean loudness step": mean(abs(s) for s in steps(m.levels)) if len(m.levels) > 1 else 0.0}


def ks_distance(a, b) -> float:
    """Kolmogorov-Smirnov distance between two samples: 0 = same distribution, 1 = no overlap."""
    a, b = np.sort(a), np.sort(b)
    grid = np.union1d(a, b)
    return float(np.abs(np.searchsorted(a, grid, side="right") / len(a)
                        - np.searchsorted(b, grid, side="right") / len(b)).max())


def compare_features(melodies: list[Melody], reference: list[Melody]) -> dict[str, dict]:
    """Mean of each per-piece feature, and its distance from the reference excerpts."""
    ours, real = [piece_features(m) for m in melodies], [piece_features(m) for m in reference]
    return {f: {"mean": mean(x[f] for x in ours),
                "ks": ks_distance([x[f] for x in ours], [x[f] for x in real])} for f in ours[0]}


# --- copying and variety ---------------------------------------------------

def view(m: Melody, name: str) -> list:
    """A melody as the sequence copying is measured on. "melody" pairs each pitch step with the length
    of the note it leads to, as in the replication: the shape and rhythm a listener would recognise."""
    if name == "pitch step":
        return steps(m.pitches)
    if name == "length":
        return m.tokens
    if name == "loudness":
        return m.levels
    lengths = [t for t in m.tokens if t[0] == "N"]
    return list(zip(steps(m.pitches), lengths[1:]))


def grams(seq: list, n: int) -> list[tuple]:
    return [tuple(seq[i:i + n]) for i in range(len(seq) - n + 1)]


class CopyIndex:
    """Finds how much of a sequence occurs verbatim in the training songs."""

    def __init__(self, sequences: list[list], n: int = 4):
        self.n = n
        self.codes: dict = {}
        data: list[int] = []
        for seq in sequences:
            data += [self.codes.setdefault(x, len(self.codes)) for x in seq] + [-1]   # -1: no run spans two songs
        self.data = np.array(data)
        self.grams = {g for seq in sequences for g in grams(seq, n)}

    def longest_run(self, seq: list) -> int:
        best, prev = 0, np.zeros(len(self.data) + 1, dtype=int)
        for x in seq:
            cur = np.zeros_like(prev)
            code = self.codes.get(x)
            if code is not None:
                cur[1:] = (self.data == code) * (prev[:-1] + 1)
            best, prev = max(best, int(cur.max())), cur
        return best


def copying(melodies: list[Melody], indexes: dict[str, CopyIndex]) -> dict[str, dict]:
    out = {}
    for name, index in indexes.items():
        seqs = [view(m, name) for m in melodies]
        runs = [index.longest_run(s) for s in seqs]
        overlap = [mean(g in index.grams for g in gs) for gs in (grams(s, index.n) for s in seqs) if gs]
        out[name] = {"longest_run": mean(runs),
                     "longest_share": mean(r / max(len(s), 1) for r, s in zip(runs, seqs)),
                     "gram_overlap": mean(overlap),
                     "full_copy": mean(r == len(s) for r, s in zip(runs, seqs))}
    return out


def diversity(melodies: list[Melody], rng: random.Random, pairs: int = 500, n: int = 4) -> dict:
    """How different the melodies are from each other: 4-gram overlap of random pairs (0 = nothing shared)."""
    out = {"unique_pieces": len({(tuple(m.tokens), tuple(m.pitches), tuple(m.levels)) for m in melodies}) / len(melodies),
           "unique_melodies": len({(tuple(m.tokens), tuple(m.pitches)) for m in melodies}) / len(melodies)}
    for name in VIEWS:
        sets = [set(grams(view(m, name), n)) for m in melodies]
        overlap = []
        for _ in range(pairs):
            a, b = rng.sample(sets, 2)
            overlap.append(len(a & b) / len(a | b) if a | b else 0.0)
        out[f"pair_overlap {name}"] = mean(overlap)
    return out
