"""Build step 1 of reports/mdp_plan.md: with no rule points, the MDP must be exactly the baseline.

On the real training songs:
- the baseline run's 200 pieces (same seed as scripts/run_baseline.py) come out identical from the MDP;
- 1,000 more pieces, one seed each, come out identical;
- every rhythm and pitch policy the pieces reach equals the baseline sampler's probabilities.

Writes results/mdp/zero_check.json.

    .venv/Scripts/python.exe -I scripts/check_mdp_zero.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from markov_music.baseline import CHAINS, fit_chains, generate_melody, next_bar_line  # noqa: E402
from markov_music.mdp import build_agents, generate_mdp_melody, onset_counts, rhythm_only  # noqa: E402
from markov_music.pop909 import Vocabulary, draw_sample, load_pool, token_length  # noqa: E402
from markov_music.theory import BAR  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from run_baseline import seed_for  # noqa: E402

OUT = ROOT / "results" / "mdp" / "zero_check.json"
ORDERS = {"length": 1, "pitch": 1, "level": 1}       # chosen by the baseline on the validation songs
RHYTHMS_FOR_ONSETS = 5000
EXTRA_PIECES = 1000


def same(a, b) -> bool:
    return (a.tokens, a.pitches, a.levels, a.tempo) == (b.tokens, b.pitches, b.levels, b.tempo)


def main() -> None:
    started = time.time()
    songs = {s.id: s for s in load_pool()}
    train_ids, _, _ = draw_sample(list(songs))
    vocabulary = Vocabulary.fit([songs[i] for i in train_ids])
    train = [vocabulary.encode(songs[i]) for i in train_ids]

    chains, mdp_chains = fit_chains(train, ORDERS), fit_chains(train, ORDERS)
    plain = build_agents(mdp_chains, {})
    rng = random.Random(seed_for("onsets"))
    counts = onset_counts([rhythm_only(plain, rng) for _ in range(RHYTHMS_FOR_ONSETS)])
    agents = build_agents(mdp_chains, counts)

    # the baseline run itself: one random stream, 200 attempts
    rng_a, rng_b = random.Random(seed_for("generate", "baseline")), random.Random(seed_for("generate", "baseline"))
    run = [same(generate_melody(chains, rng_a, f"b{i}")[0], generate_mdp_melody(agents, rng_b, f"b{i}")[0]) for i in range(200)]
    extra = [same(generate_melody(chains, random.Random(i), "x")[0], generate_mdp_melody(agents, random.Random(i), "x")[0])
             for i in range(EXTRA_PIECES)]

    rhythm_worst, rhythm_n = 0.0, 0
    model, memo = chains.models["length"], chains.memos["length"]
    for (state, left), beta in memo.items():
        if left == 0 or beta == 0:
            continue
        t = 8 * BAR - left
        expected = {}
        for a, p in model.dist(state).items():
            key = (model.next_state(state, a), left - token_length(a))
            if t + token_length(a) <= next_bar_line(t) and key in memo and p * memo[key] > 0:
                expected[a] = p * memo[key] / beta
        got = agents.rhythm.policy((state, t))
        rhythm_worst = max(rhythm_worst, max(abs(got.get(a, 0) - expected.get(a, 0)) for a in set(got) | set(expected)))
        rhythm_n += 1
    pitch_worst, pitch_n = 0.0, 0
    model, memo = chains.models["pitch"], chains.memos["pitch"]
    for (state, left), beta in memo.items():           # for pitch, "left" is notes left
        if left == 0 or beta == 0:
            continue
        expected = {a: p * memo[(model.next_state(state, a), left - 1)] / beta for a, p in model.dist(state).items()
                    if (model.next_state(state, a), left - 1) in memo and p * memo[(model.next_state(state, a), left - 1)] > 0}
        got = agents.pitch.policy((state, left))
        pitch_worst = max(pitch_worst, max(abs(got.get(a, 0) - expected.get(a, 0)) for a in set(got) | set(expected)))
        pitch_n += 1

    dead_ends = {c: sum(1 for s in {(x,) for seq in (m.sequence(c) for m in train) for x in seq}
                        if not chains.models[c].dist(s)) for c in CHAINS}
    result = {"baseline run (200 pieces, one stream): identical": sum(run), "of": len(run),
              "extra pieces (one seed each): identical": sum(extra), "of extra": len(extra),
              "rhythm policies checked": rhythm_n, "rhythm: largest probability difference": rhythm_worst,
              "pitch policies checked": pitch_n, "pitch: largest probability difference": pitch_worst,
              "values with no continuation in training (dead ends)": dead_ends,
              "states worked out": {"rhythm": len(agents.rhythm.memo), "pitch": len(agents.pitch.memo),
                                    "loudness": len(agents.loudness.memo)},
              "note starts seen in rhythm pieces": len(counts),
              "seconds": round(time.time() - started, 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    ok = all(run) and all(extra) and rhythm_worst < 1e-12 and pitch_worst < 1e-12
    print("PASS: with no rule points the MDP is exactly the baseline" if ok else "FAIL")


if __name__ == "__main__":
    main()
