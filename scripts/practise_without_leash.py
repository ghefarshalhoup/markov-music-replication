"""Build step 4 of reports/mdp_plan.md: the data only as the starting point, with no leash.

All three agents start from the data's probabilities and practise together, one whole piece at a
time, with the same rule points as the main version but no cost for moving away from the data
(NoLeashLearner). At each checkpoint, 500 pieces are made with fixed seeds and measured. For
comparison the same is done for the baseline and for the main version (with the leash).
Practice runs well past the main version's budget (10,000-30,000 pieces), to show where it heads.

Writes results/mdp/no_leash.json.

    .venv/Scripts/python.exe -I scripts/practise_without_leash.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.setrecursionlimit(10_000)

from markov_music.baseline import fit_chains, piece_features, steps  # noqa: E402
from markov_music.mdp import (NoLeashLearner, end_long, end_on_c, loudness_agent, note_starts, onset_counts,  # noqa: E402
                              pitch_agent, rhythm_agent, rule_measures, strong_beats)
from markov_music.pop909 import Melody, Vocabulary, draw_sample, load_pool  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from fit_rule_strengths import ORDERS, RHYTHMS, SEED, sample_rhythms  # noqa: E402

OUT = ROOT / "results" / "mdp" / "no_leash.json"
STRENGTHS = ROOT / "results" / "mdp" / "strengths.json"
CHECKPOINTS = (0, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000)
PIECES = 500
FEATURES = ("notes", "pitch range", "distinct pitches", "mean step size", "silent sixteenths", "loudness range",
            "mean loudness step")


def make_piece(rhythm, pitch, loudness, models, tempos, rng):
    """A piece from three agents (exact or learners); None if one gets stuck."""
    state, tokens = (models["length"].initial_state(), 0), []
    while not rhythm.is_end(state):
        a = rhythm.choose(state, rng)
        if a is None:
            return None
        tokens.append(a)
        state = rhythm.moves(state, a)[0][1]
    starts = note_starts(tokens)
    if not starts:
        return None
    state, pitches = (models["pitch"].initial_state(), len(starts)), []
    while not pitch.is_end(state):
        a = pitch.choose(state, rng)
        if a is None:
            return None
        pitches.append(a)
        state = (models["pitch"].next_state(state[0], a), state[1] - 1)
    state, levels = (models["level"].initial_state(), starts[0]), []
    for k in range(len(starts)):
        a = loudness.choose(state, rng)
        if a is None:
            return None
        levels.append(a)
        state = (models["level"].next_state(state[0], a), starts[k + 1] if k + 1 < len(starts) else None)
    return Melody("x", tokens, pitches, levels, rng.choice(tempos))


def measure(agents, models, tempos, centroids) -> dict:
    pieces = [make_piece(*agents, models, tempos, random.Random(SEED + 30_000 + i)) for i in range(PIECES)]
    done = [p for p in pieces if p]
    feats = [piece_features(p) for p in done]
    st = [abs(x) for p in done for x in steps(p.pitches)]
    return {"finished": len(done) / PIECES, "rules": rule_measures(done, centroids),
            "per piece": {f: mean(x[f] for x in feats) for f in FEATURES},
            "steps of 2 semitones or less": sum(x <= 2 for x in st) / len(st),
            "unique pieces": len({(tuple(p.tokens), tuple(p.pitches), tuple(p.levels)) for p in done}) / len(done)}


def main() -> None:
    started = time.time()
    songs = {s.id: s for s in load_pool()}
    train_ids, _, _ = draw_sample(list(songs))
    vocabulary = Vocabulary.fit([songs[i] for i in train_ids])
    chains = fit_chains([vocabulary.encode(songs[i]) for i in train_ids], ORDERS)
    models, centroids, tempos = chains.models, vocabulary.centroids, chains.tempos
    strength = json.loads(STRENGTHS.read_text(encoding="utf-8"))["strengths"]
    rules = {"length": end_long(strength["length"]), "pitch": end_on_c(strength["pitch"]),
             "level": strong_beats(strength["level"], centroids)}

    reference = {}
    base_rhythm = rhythm_agent(models["length"])
    base_counts = onset_counts(sample_rhythms(base_rhythm, models["length"], RHYTHMS, SEED))
    reference["baseline"] = measure((base_rhythm, pitch_agent(models["pitch"]), loudness_agent(models["level"], base_counts)),
                                    models, tempos, centroids)
    main_rhythm = rhythm_agent(models["length"], rules["length"])
    main_counts = onset_counts(sample_rhythms(main_rhythm, models["length"], RHYTHMS, SEED))
    reference["with the leash (main version)"] = measure(
        (main_rhythm, pitch_agent(models["pitch"], rules["pitch"]), loudness_agent(models["level"], main_counts, rules["level"])),
        models, tempos, centroids)
    for k, v in reference.items():
        print(k, json.dumps(v), flush=True)

    learners = (NoLeashLearner(rhythm_agent(models["length"], rules["length"])),
                NoLeashLearner(pitch_agent(models["pitch"], rules["pitch"])),
                NoLeashLearner(loudness_agent(models["level"], {}, rules["level"])))
    rhythm, pitch, loudness = learners
    rng, curve, stuck = random.Random(SEED + 3), {}, 0
    for k in range(CHECKPOINTS[-1] + 1):
        if k in CHECKPOINTS:
            curve[k] = measure(learners, models, tempos, centroids) | {"seconds": round(time.time() - started, 1)}
            print(k, json.dumps(curve[k]), flush=True)
        tokens = rhythm.practise((models["length"].initial_state(), 0), lambda s, a, i: rhythm.moves(s, a)[0][1], rng)
        if tokens is None:
            stuck += 1
            continue
        starts = note_starts(tokens)
        if not starts:
            continue
        pitch.practise((models["pitch"].initial_state(), len(starts)),
                       lambda s, a, i: (models["pitch"].next_state(s[0], a), s[1] - 1), rng)
        loudness.practise((models["level"].initial_state(), starts[0]),
                          lambda s, a, i: (models["level"].next_state(s[0], a), starts[i + 1] if i + 1 < len(starts) else None), rng)

    result = {"strengths": strength, "reference": reference, "without the leash, by practice pieces": curve,
              "practice pieces where the rhythm got stuck": stuck, "seconds": round(time.time() - started, 1)}
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("done", result["seconds"])


if __name__ == "__main__":
    main()
