"""Build step 2 of reports/mdp_plan.md: find each rule's strength, then run the strength sweep.

Each strength is the value at which the agent follows its rule as often as the real training songs do.
The targets were fixed beforehand by scripts/check_reward_rules.py (results/reward_rules/checks.json):
    rhythm    share of songs whose last note is a half note or longer
    pitch     share of songs whose last note is a C
    loudness  velocity on beats 1 and 3 minus velocity off the beat, per song
Rhythm and pitch are matched with exact chances; loudness by sampling pieces with fixed seeds.
Only training songs are read. Then every strength is multiplied by 0, 0.5, 1, 2 and 4.

Writes results/mdp/strengths.json.

    .venv/Scripts/python.exe -I scripts/fit_rule_strengths.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.setrecursionlimit(10_000)

from markov_music.baseline import fit_chains, piece_features  # noqa: E402
from markov_music.mdp import (Agents, end_long, end_on_c, expected, generate_mdp_melody, kl, loudness_agent,  # noqa: E402
                              note_starts, notes_done, onset_counts, pitch_agent, policy_change, rhythm_agent,
                              rule_measures, strong_beats, strong_minus_offbeat, time_used)
from markov_music.pop909 import Melody, Vocabulary, draw_sample, load_pool  # noqa: E402

OUT = ROOT / "results" / "mdp" / "strengths.json"
CHECKS = ROOT / "results" / "reward_rules" / "checks.json"
ORDERS = {"length": 1, "pitch": 1, "level": 1}
MULTIPLIERS = (0, 0.5, 1, 2, 4)
RHYTHMS = 5000              # rhythm pieces used for note counts and note starts
LOUDNESS_PIECES = 2000      # pieces used to match the loudness rule
SWEEP_PIECES = 1000
SEED = 20261117


def bisect(f, target: float, hi: float, steps: int) -> float:
    """Strength at which the increasing function f reaches the target."""
    lo = 0.0
    while f(hi) < target:
        lo, hi = hi, 2 * hi
    for _ in range(steps):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < target else (lo, mid)
    return (lo + hi) / 2


def sample_rhythms(agent, model, n, seed):
    rng, out = random.Random(seed), []
    for _ in range(n):
        state, tokens = (model.initial_state(), 0), []
        while not agent.is_end(state):
            a = agent.choose(state, rng)
            tokens.append(a)
            state = agent.moves(state, a)[0][1]
        out.append(tokens)
    return out


def pitch_chance_of_c(agent, model, note_counts: Counter) -> float:
    total = sum(note_counts.values())
    return sum(c * expected(agent, (model.initial_state(), n), notes_done, lambda s, a: s[1] == 1 and a % 12 == 0)
               for n, c in note_counts.items()) / total


def sample_levels(agent, model, rhythms, seed):
    """Levels for the given rhythms, one fixed seed per piece."""
    out = []
    for i, tokens in enumerate(rhythms):
        rng, starts = random.Random(seed + i), note_starts(tokens)
        state, levels = (model.initial_state(), starts[0]), []
        for k in range(len(starts)):
            a = agent.choose(state, rng)
            levels.append(a)
            state = (model.next_state(state[0], a), starts[k + 1] if k + 1 < len(starts) else None)
        out.append(levels)
    return out


def main() -> None:
    started = time.time()
    songs = {s.id: s for s in load_pool()}
    train_ids, _, _ = draw_sample(list(songs))
    vocabulary = Vocabulary.fit([songs[i] for i in train_ids])
    train = [vocabulary.encode(songs[i]) for i in train_ids]
    chains = fit_chains(train, ORDERS)
    models, centroids = chains.models, vocabulary.centroids
    checks = json.loads(CHECKS.read_text(encoding="utf-8"))
    targets = {"ends on a long note": checks["C ending on a long note"]["real: last note of the song"]["share >= 8"],
               "ends on C": checks["B ending on C"]["real"]["last note of the song"]["C"],
               "strong beats minus offbeats": checks["D louder on strong beats"]["real: strong beats minus offbeats, per song"]["velocity"]}
    print("targets:", targets, flush=True)
    r_start = (models["length"].initial_state(), 0)

    # rhythm: exact chance of ending on a long note
    def rhythm_rate(s):
        return expected(rhythm_agent(models["length"], end_long(s)), r_start, time_used, lambda st, a: end_long(1.0)(st, a) > 0)
    strength = {"length": bisect(rhythm_rate, targets["ends on a long note"], 1.0, 40)}
    print("rhythm strength", strength["length"], flush=True)

    # pitch: exact chance of ending on C, over the note counts of the tuned rhythm agent's pieces
    rhythms = sample_rhythms(rhythm_agent(models["length"], end_long(strength["length"])), models["length"], RHYTHMS, SEED)
    note_counts = Counter(sum(t[0] == "N" for t in r) for r in rhythms)
    strength["pitch"] = bisect(lambda s: pitch_chance_of_c(pitch_agent(models["pitch"], end_on_c(s)), models["pitch"], note_counts),
                               targets["ends on C"], 1.0, 40)
    print("pitch strength", strength["pitch"], flush=True)

    # loudness: sampled, with the same seeds for every strength tried
    counts = onset_counts(rhythms)
    fixed = rhythms[:LOUDNESS_PIECES]

    def loudness_gap(s):
        agent = loudness_agent(models["level"], counts, strong_beats(s, centroids))
        gaps = []
        for tokens, levels in zip(fixed, sample_levels(agent, models["level"], fixed, SEED)):
            g =strong_minus_offbeat(Melody("x", tokens, [0] * len(levels), levels), centroids)
            if g is not None:
                gaps.append(g)
        return mean(gaps)
    strength["level"] = bisect(loudness_gap, targets["strong beats minus offbeats"], 0.02, 25)
    print("loudness strength", strength["level"], flush=True)

    # sweep: full pieces at each multiple of the matched strengths
    sweep = {}
    base_rhythm, base_pitch = rhythm_agent(models["length"]), pitch_agent(models["pitch"])
    for m in MULTIPLIERS:
        r_agent = rhythm_agent(models["length"], end_long(m * strength["length"]))
        p_agent = pitch_agent(models["pitch"], end_on_c(m * strength["pitch"]))
        sweep_rhythms = sample_rhythms(r_agent, models["length"], RHYTHMS, SEED + 1)
        l_agent = loudness_agent(models["level"], onset_counts(sweep_rhythms), strong_beats(m * strength["level"], centroids))
        base_loud = loudness_agent(models["level"], onset_counts(sweep_rhythms))
        agents = Agents(r_agent, p_agent, l_agent, models, chains.tempos)
        pieces = [generate_mdp_melody(agents, random.Random(SEED + 10_000 + i), f"x{i}")[0] for i in range(SWEEP_PIECES)]
        n_counts = Counter(len(p.pitches) for p in pieces)
        loud_kl = []
        for p in pieces:
            starts, bits = note_starts(p.tokens), 0.0
            state = (models["level"].initial_state(), starts[0])
            for k, a in enumerate(p.levels):
                bits += kl(l_agent.policy(state), base_loud.policy(state))
                state = (models["level"].next_state(state[0], a), starts[k + 1] if k + 1 < len(starts) else None)
            loud_kl.append(bits)
        feats = [piece_features(p) for p in pieces]
        sweep[str(m)] = {
            "rules": rule_measures(pieces, centroids),
            "bits changed per piece (KL from the baseline)": {
                "rhythm": policy_change(r_agent, base_rhythm, r_start, time_used),
                "pitch": sum(c * policy_change(p_agent, base_pitch, (models["pitch"].initial_state(), n), notes_done)
                             for n, c in n_counts.items()) / len(pieces),
                "loudness": mean(loud_kl)},
            "per piece": {f: mean(x[f] for x in feats) for f in ("notes", "pitch range", "distinct pitches", "mean step size",
                                                                  "loudness range", "mean loudness step")},
            "unique pieces": len({(tuple(p.tokens), tuple(p.pitches), tuple(p.levels)) for p in pieces}) / len(pieces)}
        print(m, json.dumps(sweep[str(m)]), flush=True)

    result = {"targets (real training songs)": targets, "strengths": strength, "sweep": sweep,
              "seconds": round(time.time() - started, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
