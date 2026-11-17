"""Check candidate MDP reward rules on the 80 TRAINING songs (validation and test songs are not read).

For each rule: do real songs follow it, does the baseline (n = 1) already do it, and how large is the gap?
Also: where the silence in real excerpts comes from, and what our bar rule does to generated rhythm.
The numbers are quoted in reports/mdp_plan.md.

    .venv/Scripts/python.exe -I scripts/check_reward_rules.py
"""
from __future__ import annotations

import bisect
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.setrecursionlimit(10_000)

from markov_music.baseline import fit_chains, generate_melody, next_bar_line, steps  # noqa: E402
from markov_music.pop909 import (WINDOW_BARS, WINDOW_MIN_NOTES, Vocabulary, _song_median, bar_windows,  # noqa: E402
                                 draw_sample, load_pool, note_tokens, token_length, tonic_shift)
from markov_music.theory import BAR, MAJOR_SCALE  # noqa: E402

OUT = ROOT / "results" / "reward_rules" / "checks.json"
N_PIECES = 1000
PIECE_SEED, RHYTHM_SEED, NULL_SEED = 20261109, 7, 1
LONG = 8                       # a half note, in sixteenths
OCTAVE = 12


def summary(x) -> dict:
    x = np.asarray(x, dtype=float)
    return {"mean": float(x.mean()), "sd": float(x.std()), "p5": float(np.percentile(x, 5)),
            "p50": float(np.percentile(x, 50)), "p95": float(np.percentile(x, 95)), "n": int(len(x))}


def share_in(pitches, classes) -> float:
    return float(np.mean([p % 12 in classes for p in pitches]))


def bar_of(lines: list[int], t: int) -> int | None:
    """Index of the 16-sixteenth bar containing time t, or None outside steady bars."""
    i = bisect.bisect_right(lines, t) - 1
    return i if 0 <= i < len(lines) - 1 and lines[i + 1] - lines[i] == BAR else None


def beat_class(position: int) -> str:
    return {0: "beat 1", 8: "beat 3", 4: "beats 2 and 4", 12: "beats 2 and 4"}.get(
        position, "eighth offbeats" if position % 2 == 0 else "sixteenth offbeats")


STRONG, OFFBEAT = ("beat 1", "beat 3"), ("eighth offbeats", "sixteenth offbeats")
CLASSES = ("beat 1", "beat 3", "beats 2 and 4", "eighth offbeats", "sixteenth offbeats")


def sample_rhythm(model, allowed, rng: random.Random, memo: dict, total: int = WINDOW_BARS * BAR) -> list[str]:
    """Exact constrained sampling as in markov_music.generate, with a rule that may treat notes and rests differently."""
    def options(state, t):
        for sym, p in model.dist(state).items():
            t2 = t + token_length(sym)
            if t2 <= total and allowed(sym, t, t2):
                yield sym, p, model.next_state(state, sym), t2

    def beta(state, t):
        if (state, t) not in memo:
            memo[state, t] = 1.0 if t == total else sum(p * beta(n, t2) for _, p, n, t2 in options(state, t))
        return memo[state, t]

    state, t, out = model.initial_state(), 0, []
    while t < total:
        choices = [(sym, n, t2, p * beta(n, t2)) for sym, p, n, t2 in options(state, t)]
        sym, state, t, _ = rng.choices(choices, weights=[c[3] for c in choices], k=1)[0]
        out.append(sym)
    return out


def main() -> None:
    songs = {s.id: s for s in load_pool()}
    train_ids, _, _ = draw_sample(list(songs))
    train_songs = [songs[i] for i in train_ids]
    vocabulary = Vocabulary.fit(train_songs)
    train = [vocabulary.encode(s) for s in train_songs]
    windows = []                                   # (song, start, notes): the same excerpts as bar_windows
    for s in train_songs:
        for a, b in zip(s.bar_lines[::WINDOW_BARS], s.bar_lines[WINDOW_BARS::WINDOW_BARS]):
            notes = [n for n in s.notes if a <= n[1] < b]
            if b - a == WINDOW_BARS * BAR and len(notes) >= WINDOW_MIN_NOTES:
                windows.append((s, a, notes))
    assert [w for _, _, w in windows] == [w for s in train_songs for w in bar_windows(s)]
    excerpts = [vocabulary.encode(s, w) for s, _, w in windows]
    chains = fit_chains(train, {"length": 1, "pitch": 1, "level": 1})
    rng = random.Random(PIECE_SEED)
    base = [generate_melody(chains, rng, f"b{i}")[0] for i in range(N_PIECES)]
    R: dict = {"training songs": len(train_songs), "training excerpts": len(excerpts), "baseline pieces": len(base)}

    # --- A. Range ------------------------------------------------------------------------------
    pitches = np.array([p for m in train for p in m.pitches])
    A: dict = {"range per excerpt": {"real": summary([max(m.pitches) - min(m.pitches) for m in excerpts]),
                                     "baseline": summary([max(m.pitches) - min(m.pitches) for m in base])},
               "middle pitch per excerpt": {"real": summary([np.median(m.pitches) for m in excerpts]),
                                            "baseline": summary([np.median(m.pitches) for m in base])}}
    bands = {}
    for width in (13, 15, 19, 21):
        lo = max(range(40, 90), key=lambda lo: mean(all(lo <= p <= lo + width for p in m.pitches) for m in excerpts))
        bands[width] = {"band": [lo, lo + width],
                        "real excerpts fully inside": mean(all(lo <= p <= lo + width for p in m.pitches) for m in excerpts),
                        "baseline pieces fully inside": mean(all(lo <= p <= lo + width for p in m.pitches) for m in base)}
    A["one fixed band, best placement"] = bands
    for name, ms in (("real", excerpts), ("baseline", base)):
        far = np.array([max(abs(p - m.pitches[0]) for p in m.pitches) for m in ms])
        each = np.array([abs(p - m.pitches[0]) for m in ms for p in m.pitches])
        A.setdefault("distance from the piece's first note", {})[name] = {
            "farthest note": summary(far), "notes within an octave": float(np.mean(each <= OCTAVE)),
            "pieces fully within an octave": float(np.mean(far <= OCTAVE))}
    centre = float(np.median(pitches))
    for name, ms in (("real", train), ("baseline", base)):
        own, fixed, step = [], [], []
        for m in ms:
            c = np.median(m.pitches)
            for a, b in zip(m.pitches, m.pitches[1:]):
                own.append(a - c)
                fixed.append(a - centre)
                step.append(b - a)
        A.setdefault("pull back to the middle (slope of next step on distance)", {})[name] = {
            "own middle": float(np.polyfit(own, step, 1)[0]), "one fixed middle": float(np.polyfit(fixed, step, 1)[0])}
    R["A range"] = A

    # --- B. Ending on the home note -----------------------------------------------------------------
    rows = defaultdict(list)
    per_song = []
    for s in train_songs:
        p = [n[3] + tonic_shift(s.keys[0][2]) for n in s.notes]
        rows["last note of the song"].append(p[-1])
        before_rest = []
        for i, (cur, nxt) in enumerate(zip(s.notes, s.notes[1:])):
            gap = nxt[1] - cur[2]
            for label, least in (("before a rest of 1 beat or more", 4), ("before a rest of 2 beats or more", 8),
                                 ("before a rest of 1 bar or more", 16)):
                if gap >= least:
                    rows[label].append(p[i])
            if gap >= 4:
                before_rest.append(p[i])
        if len(before_rest) >= 5:
            per_song.append(share_in(before_rest, {0}) > share_in(p, {0}))
    rows["all notes"] = list(pitches)
    rows["last note of an 8-bar excerpt"] = [m.pitches[-1] for m in excerpts]
    B = {"real": {k: {"C": share_in(v, {0}), "C, E or G": share_in(v, {0, 4, 7}), "n": len(v)} for k, v in rows.items()},
         "songs with C more common before rests than overall": {"share": mean(per_song), "songs": len(per_song)},
         "pitch class of the song's last note": dict(Counter(p % 12 for p in rows["last note of the song"]).most_common())}
    finals = [m.pitches[-1] for m in base]
    B["baseline"] = {"all notes": {"C": share_in([p for m in base for p in m.pitches], {0})},
                     "last note of the piece": {"C": share_in(finals, {0}), "C, E or G": share_in(finals, {0, 4, 7})}}
    R["B ending on C"] = B

    # --- C. Ending on a long note -------------------------------------------------------------------
    def lengths(x):
        x = np.array(x)
        return {"median": float(np.median(x)), f"share >= {LONG}": float(np.mean(x >= LONG)), "n": int(len(x))}
    R["C ending on a long note"] = {
        "real: last note of the song": lengths([s.notes[-1][2] - s.notes[-1][1] for s in train_songs]),
        "real: note before a rest of 1 bar or more": lengths([c[2] - c[1] for s in train_songs for c, n in zip(s.notes, s.notes[1:]) if n[1] - c[2] >= 16]),
        "real: all notes": lengths([n[2] - n[1] for s in train_songs for n in s.notes]),
        "baseline: last note of the piece": lengths([token_length([t for t in m.tokens if t[0] == "N"][-1]) for m in base]),
        "baseline: pieces ending on a rest": mean(m.tokens[-1][0] == "R" for m in base)}

    # --- D. Louder on strong beats ------------------------------------------------------------------
    notes_by_class, song_diffs, by_length = defaultdict(list), [], defaultdict(lambda: defaultdict(list))
    for s, m in zip(train_songs, train):
        median, sv = _song_median(s), defaultdict(list)
        note_lengths = [token_length(t) for t in m.tokens if t[0] == "N"]
        for n, level, length in zip(s.notes, m.levels, note_lengths):
            i = bar_of(s.bar_lines, n[1])
            if i is None:
                continue
            c = beat_class(n[1] - s.bar_lines[i])
            notes_by_class[c].append((n[4] - median, level))
            sv[c].append(n[4] - median)
            by_length[length][c].append(n[4] - median)
        strong, weak = sum((sv[c] for c in STRONG), []), sum((sv[c] for c in OFFBEAT), [])
        if len(strong) >= 10 and len(weak) >= 10:
            song_diffs.append(mean(strong) - mean(weak))
    total = sum(len(v) for v in notes_by_class.values())
    spread = float(np.std([v for c in notes_by_class.values() for v, _ in c]))
    D = {"real, by position in the bar": {c: {"share of notes": len(notes_by_class[c]) / total,
                                              "velocity above the song's median": float(np.mean([v for v, _ in notes_by_class[c]])),
                                              "level": float(np.mean([lv for _, lv in notes_by_class[c]]))} for c in CLASSES},
         "real: strong beats minus offbeats, per song": {"velocity": float(np.mean(song_diffs)),
                                                         "in units of the usual spread": float(np.mean(song_diffs)) / spread,
                                                         "songs where strong beats are louder": int(np.sum(np.array(song_diffs) > 0)),
                                                         "songs": len(song_diffs)},
         "real: same, notes of one length only": {
             L: float(np.mean(sum((by_length[L][c] for c in STRONG), [])) - np.mean(sum((by_length[L][c] for c in OFFBEAT), [])))
             for L in (2, 4)}}
    bl = defaultdict(list)
    for m in base:
        t, k = 0, 0
        for x in m.tokens:
            if x[0] == "N":
                bl[beat_class(t % BAR)].append(vocabulary.centroids[m.levels[k]])
                k += 1
            t += token_length(x)
    D["baseline: velocity above the median, by position"] = {c: float(np.mean(bl[c])) for c in CLASSES}
    D["baseline: strong beats minus offbeats"] = float(np.mean(sum((bl[c] for c in STRONG), [])) - np.mean(sum((bl[c] for c in OFFBEAT), [])))
    R["D louder on strong beats"] = D

    # --- E. Silence ---------------------------------------------------------------------------------
    parts = defaultdict(list)
    for (s, a, w), m in zip(windows, excerpts):
        raw = note_tokens(w)
        parts["before the first note"].append(w[0][1] - a)
        parts["after the last note"].append(a + WINDOW_BARS * BAR - w[-1][2])
        parts["rests between notes"].append(sum(token_length(t) for t in raw if t[0] == "R"))
        parts["long notes shortened to a kept length"].append(sum(token_length(t) for t in raw if t[0] == "N")
                                                              - sum(token_length(t) for t in m.tokens if t[0] == "N"))
        parts["total, as in the baseline report"].append(WINDOW_BARS * BAR - sum(token_length(t) for t in m.tokens if t[0] == "N"))
    E: dict = {"real excerpts: silent sixteenths by where they are": {k: float(np.mean(v)) for k, v in parts.items()}}
    rests, crossing, starts, bars_by_song = [], [], [], []
    for s in train_songs:
        bars = []
        for cur, nxt in zip(s.notes, s.notes[1:]):
            if nxt[1] - cur[2] < 4:
                continue
            rests.append(nxt[1] - cur[2])
            crossing.append(any(cur[2] < x < nxt[1] for x in s.bar_lines))
            i = bar_of(s.bar_lines, cur[2])
            if i is not None:
                starts.append(cur[2] - s.bar_lines[i])
                bars.append(i)
        bars_by_song.append(bars)
    rests, crossing = np.array(rests), np.array(crossing)
    E["real rests (whole training songs)"] = {
        "count": int(len(rests)), "length": summary(rests), "share crossing a bar line": float(crossing.mean()),
        "share of rest time in rests crossing a bar line": float(rests[crossing].sum() / rests.sum()),
        "where in the bar they start (sixteenth 0-15)": dict(sorted(Counter(starts).items()))}
    null_rng = np.random.default_rng(NULL_SEED)
    for period in (2, 3, 4, 8):
        real, chance = [], []
        for bars in bars_by_song:
            if len(bars) < 8:
                continue
            c = np.bincount(np.array(bars) % period, minlength=period)
            real.append(c.max() / c.sum())
            chance.append((null_rng.multinomial(len(bars), [1 / period] * period, size=2000).max(axis=1) / len(bars)).mean())
        E.setdefault("rests repeating every k bars: share at the busiest phase", {})[period] = {
            "real": float(np.mean(real)), "if rests fell in random bars": float(np.mean(chance)), "songs": len(real)}
    real_lengths = Counter(t for m in train for t in m.tokens)
    rules = {"no note or rest crosses a bar line (baseline)": lambda sym, t, t2: t2 <= next_bar_line(t),
             "rests may cross bar lines, notes may not": lambda sym, t, t2: sym[0] == "R" or t2 <= next_bar_line(t),
             "no bar rule": lambda sym, t, t2: True}
    for name, allowed in rules.items():
        rng, memo = random.Random(RHYTHM_SEED), {}
        pieces = [sample_rhythm(chains.models["length"], allowed, rng, memo) for _ in range(N_PIECES)]
        counts, downbeats, bars_with_notes = Counter(), 0, 0
        for toks in pieces:
            counts.update(toks)
            t, onsets = 0, set()
            for x in toks:
                if x[0] == "N":
                    onsets.add(t)
                t += token_length(x)
            for b in range(0, t, BAR):
                if any(b <= o < b + BAR for o in onsets):
                    bars_with_notes += 1
                    downbeats += b in onsets
        g, r = {k: v / sum(counts.values()) for k, v in counts.items()}, {k: v / sum(real_lengths.values()) for k, v in real_lengths.items()}
        E.setdefault("generated rhythm under each bar rule", {})[name] = {
            "silent sixteenths": float(np.mean([sum(token_length(x) for x in p if x[0] == "R") for p in pieces])),
            "notes per piece": float(np.mean([sum(x[0] == "N" for x in p) for p in pieces])),
            "bars with a note on beat 1": downbeats / bars_with_notes,
            "length distance from training songs (TV)": 0.5 * sum(abs(g.get(k, 0) - r.get(k, 0)) for k in set(g) | set(r))}
    downbeats = bars = 0
    for s, a, w in windows:
        onsets = {n[1] - a for n in w}
        for b in range(0, WINDOW_BARS * BAR, BAR):
            if any(b <= o < b + BAR for o in onsets):
                bars += 1
                downbeats += b in onsets
    E["real excerpts: bars with a note on beat 1"] = downbeats / bars
    R["E silence"] = E

    # --- F. Already matched by the baseline (no rule needed) -----------------------------------------
    def generated_onsets(m):
        t, out = 0, []
        for x in m.tokens:
            if x[0] == "N":
                out.append(t)
            t += token_length(x)
        return out
    real_onsets = [[n[1] - a for n in w] for _, a, w in windows]          # measured from the excerpt's bar line
    for name, ms, ons in (("real excerpts", excerpts, real_onsets), ("baseline", base, [generated_onsets(m) for m in base])):
        st = np.array([abs(x) for m in ms for x in steps(m.pitches)])
        onsets = Counter(beat_class(t % BAR) for o in ons for t in o)
        R.setdefault("F already matched", {})[name] = {
            "steps of 2 semitones or less": float(np.mean(st <= 2)), "repeated notes": float(np.mean(st == 0)),
            "leaps of more than 7 semitones": float(np.mean(st > 7)),
            "notes in C major": float(np.mean([p % 12 in MAJOR_SCALE for m in ms for p in m.pitches])),
            "note onsets on beat 1": onsets["beat 1"] / sum(onsets.values()),
            "note onsets on sixteenth offbeats": onsets["sixteenth offbeats"] / sum(onsets.values())}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(R, indent=1), encoding="utf-8")
    print(json.dumps(R, indent=1))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
