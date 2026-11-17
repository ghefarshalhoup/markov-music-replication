"""Build step 3 of reports/mdp_plan.md: learn each agent's behaviour by practice (soft Q-learning) and
check it against the exact answer key.

Each agent starts from the data's probabilities (Q = 0) and makes pieces, with the matched rule
strengths from results/mdp/strengths.json. Every CHECK pieces the distance from the exact answer is
measured: KL(exact || practised) in bits per choice, over the states the exact behaviour visits.
Practice stops when that is at most STOP bits per choice, or after MAX pieces.
The world for the pitch and loudness agents is a fixed pool of rhythms from the tuned rhythm agent.
Finally 1,000 pieces from the practised agents are compared with 1,000 from the exact ones.

Writes results/mdp/practice.json.

    .venv/Scripts/python.exe -I scripts/practise_agents.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.setrecursionlimit(10_000)

from markov_music.baseline import fit_chains  # noqa: E402
from markov_music.mdp import (Agents, SoftQLearner, end_long, end_on_c, gap_to_exact, generate_mdp_melody,  # noqa: E402
                              loudness_agent, note_start, note_starts, notes_done, onset_counts, pitch_agent,
                              rhythm_agent, rule_measures, strong_beats, time_used)
from markov_music.pop909 import Vocabulary, draw_sample, load_pool  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from fit_rule_strengths import ORDERS, RHYTHMS, SEED, sample_rhythms  # noqa: E402

OUT = ROOT / "results" / "mdp" / "practice.json"
STRENGTHS = ROOT / "results" / "mdp" / "strengths.json"
CHECK = 10_000
MAX = 300_000
STOP = 0.01
PIECES = 1000


def train(name, learner, exact, start_of, step, starts, progress, rng):
    curve, began = [], time.time()
    for k in range(1, MAX + 1):
        learner.practise(start_of(k), lambda s, a, i: step(k, s, a, i), rng)
        if k % CHECK == 0:
            gap = gap_to_exact(learner, exact, starts, progress)
            curve.append({"pieces": k, **gap, "seconds": round(time.time() - began, 1)})
            print(name, curve[-1], flush=True)
            if gap["bits per choice"] <= STOP:
                break
    return curve


def main() -> None:
    songs = {s.id: s for s in load_pool()}
    train_ids, _, _ = draw_sample(list(songs))
    vocabulary = Vocabulary.fit([songs[i] for i in train_ids])
    chains = fit_chains([vocabulary.encode(songs[i]) for i in train_ids], ORDERS)
    models, centroids = chains.models, vocabulary.centroids
    strength = json.loads(STRENGTHS.read_text(encoding="utf-8"))["strengths"]
    rules = {"length": end_long(strength["length"]), "pitch": end_on_c(strength["pitch"]),
             "level": strong_beats(strength["level"], centroids)}

    exact_rhythm = rhythm_agent(models["length"], rules["length"])
    pool = sample_rhythms(exact_rhythm, models["length"], RHYTHMS, SEED)        # the world for pitch and loudness
    counts = onset_counts(pool)
    note_counts = Counter(sum(t[0] == "N" for t in r) for r in pool)
    exact = {"length": exact_rhythm, "pitch": pitch_agent(models["pitch"], rules["pitch"]),
             "level": loudness_agent(models["level"], counts, rules["level"])}
    learners = {c: SoftQLearner(type_(models[c], *extra, rules[c]))
                for c, type_, extra in (("length", rhythm_agent, ()), ("pitch", pitch_agent, ()), ("level", loudness_agent, (counts,)))}
    starts_of_pool = [note_starts(r) for r in pool]
    rng = random.Random(SEED + 2)
    curves = {}

    r0 = (models["length"].initial_state(), 0)
    curves["rhythm"] = train("rhythm", learners["length"], exact["length"], lambda k: r0,
                             lambda k, s, a, i: learners["length"].moves(s, a)[0][1], [(r0, 1)], time_used, rng)

    p_init = models["pitch"].initial_state()
    curves["pitch"] = train("pitch", learners["pitch"], exact["pitch"],
                            lambda k: (p_init, len(starts_of_pool[k % len(pool)])),
                            lambda k, s, a, i: (models["pitch"].next_state(s[0], a), s[1] - 1),
                            [((p_init, n), c) for n, c in note_counts.items()], notes_done, rng)

    l_init = models["level"].initial_state()
    first = Counter(st[0] for st in starts_of_pool)

    def loud_step(k, s, a, i):
        st = starts_of_pool[k % len(pool)]
        return models["level"].next_state(s[0], a), st[i + 1] if i + 1 < len(st) else None
    curves["loudness"] = train("loudness", learners["level"], exact["level"], lambda k: (l_init, starts_of_pool[k % len(pool)][0]),
                               loud_step, [((l_init, t), c) for t, c in first.items()], note_start, rng)

    compare = {}
    for label, group in (("exact", exact), ("practised", learners)):
        agents = Agents(group["length"], group["pitch"], group["level"], models, chains.tempos)
        pieces = [generate_mdp_melody(agents, random.Random(SEED + 20_000 + i), f"x{i}")[0] for i in range(PIECES)]
        compare[label] = rule_measures([p for p in pieces if p], centroids) | {"finished": sum(p is not None for p in pieces) / PIECES}
        print(label, compare[label], flush=True)

    result = {"strengths": strength, "stop rule": {"bits per choice at most": STOP, "max pieces": MAX, "check every": CHECK},
              "learning curves": curves, "rules: exact vs practised (same seeds)": compare,
              "states learned": {c: len(l.q) for c, l in learners.items()}}
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
