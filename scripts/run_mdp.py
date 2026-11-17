"""Build step 5 of reports/mdp_plan.md: every condition, measured exactly as the baseline was.

Conditions (section 5 of the plan), 200 attempts each with fixed seeds:
    baseline (n = 1)                        the MDP with no rule points (shown identical in check_mdp_zero)
    MDP main, practised                     soft Q-learning to the stop rule, matched strengths
    MDP main, exact                         the answer key, reported alongside
    MDP 0.5x, 2x, 4x                        the strength sweep (exact; practice matched exact at 1x)
    MDP without one rule (x3)               which rule causes which effect (exact)
    no leash                                data only as the starting point, practised as long as the main version
    baseline, rhythm memory 2               optional; added after seeing the baseline's results
Measures: the baseline's (distance from the test songs, entropy, per-piece features with the corrected
silence measure, copying per view, variety) plus the rules and how far each policy moved from the
baseline's (KL bits per piece, along the generated pieces). The test songs are read here for the first time.

Writes results/mdp/results.json, summary.md and examples/*.mid.

    .venv/Scripts/python.exe -I scripts/run_mdp.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.setrecursionlimit(10_000)

from markov_music.baseline import (STATISTICS, VIEWS, CopyIndex, compare_features, copying, distributions,  # noqa: E402
                                   diversity, entropy, fit_chains, group_tv, view)
from markov_music.mdp import (NoLeashLearner, SoftQLearner, end_long, end_on_c, gap_to_exact, kl, loudness_agent, note_starts,  # noqa: E402
                              onset_counts, pitch_agent, rhythm_agent, rule_measures, strong_beats)
from markov_music.musicxml_io import write_midi  # noqa: E402
from markov_music.pop909 import Melody, Vocabulary, bar_windows, draw_sample, load_pool, pool_checks, to_events, token_length  # noqa: E402
from fit_rule_strengths import RHYTHMS, SEED, sample_rhythms  # noqa: E402
from practise_without_leash import make_piece  # noqa: E402
from run_baseline import COPY_SAMPLE, GROUP_PIECES, GROUP_REPEATS, REAL_GROUP_REPEATS, seed_for, verify_pool  # noqa: E402

OUT = ROOT / "results" / "mdp"
STRENGTHS = OUT / "strengths.json"
ATTEMPTS = 200
STOP, CHECK, MAX = 0.01, 10_000, 300_000        # practice stop rule, as in practise_agents.py
NO_LEASH_PIECES = 30_000                       # the main version's largest practice budget
EXPORT = {"MDP main (practised)": 5, "MDP 4x": 3, "no leash": 3, "baseline": 3}
LISTEN = ("baseline", "MDP main (practised)")   # their first 10 pieces are the listening-test clips
LISTEN_PIECES = 10


def rests_between_notes(m: Melody) -> int:
    """The corrected silence measure: rests between notes only, the same for real and generated pieces."""
    return sum(token_length(t) for t in m.tokens if t[0] == "R")


def practise(learner, exact_agent, start_of, step, starts, progress, rng):
    for k in range(1, MAX + 1):
        learner.practise(start_of(k), lambda s, a, i: step(k, s, a, i), rng)
        if k % CHECK == 0 and gap_to_exact(learner, exact_agent, starts, progress)["bits per choice"] <= STOP:
            return k
    return MAX


def policy_bits(pieces, agents, baselines, models) -> dict:
    """KL(agent || baseline) in bits per piece, summed over the choices each piece made, per agent.
    Choices the baseline would never make are counted separately."""
    bits, never = defaultdict(list), Counter()
    for p in pieces:
        walk = {"rhythm": [], "pitch": [], "loudness": []}
        s = (models["length"].initial_state(), 0)
        for a in p.tokens:
            walk["rhythm"].append(s)
            s = (models["length"].next_state(s[0], a), s[1] + token_length(a))
        s = (models["pitch"].initial_state(), len(p.pitches))
        for a in p.pitches:
            walk["pitch"].append(s)
            s = (models["pitch"].next_state(s[0], a), s[1] - 1)
        starts = note_starts(p.tokens)
        s = (models["level"].initial_state(), starts[0])
        for k, a in enumerate(p.levels):
            walk["loudness"].append(s)
            s = (models["level"].next_state(s[0], a), starts[k + 1] if k + 1 < len(starts) else None)
        for part, states in walk.items():
            total = 0.0
            for s in states:
                pol, base = agents[part].policy(s), baselines[part].policy(s)
                if not base:                       # a state the baseline never reaches
                    never[part] += 1
                    continue
                if any(a not in base for a, v in pol.items() if v > 1e-12):
                    never[part] += 1
                    pol = {a: v for a, v in pol.items() if a in base}
                    z = sum(pol.values())
                    pol = {a: v / z for a, v in pol.items()}
                total += kl(pol, base)
            bits[part].append(total)
    return {"bits per piece": {k: mean(v) for k, v in bits.items()}, "choices the baseline rules out": dict(never)}


def main() -> None:
    started = time.time()
    songs = load_pool()
    verify_pool(pool_checks(songs))
    by_id = {s.id: s for s in songs}
    train_ids, _, test_ids = draw_sample(list(by_id))
    vocabulary = Vocabulary.fit([by_id[i] for i in train_ids])
    train = [vocabulary.encode(by_id[i]) for i in train_ids]
    test = [vocabulary.encode(by_id[i]) for i in test_ids]

    def windows(ids):
        return [vocabulary.encode(by_id[i], w, f"{i}_{k}") for i in ids for k, w in enumerate(bar_windows(by_id[i]))]
    train_windows, test_windows = windows(train_ids), windows(test_ids)
    centroids = vocabulary.centroids
    strength = json.loads(STRENGTHS.read_text(encoding="utf-8"))["strengths"]
    chains = fit_chains(train, {"length": 1, "pitch": 1, "level": 1})
    models, tempos = chains.models, chains.tempos
    test_dists = distributions(test)
    indexes = {name: CopyIndex([view(m, name) for m in train]) for name in VIEWS}

    def rules(mult: float = 1.0, drop: str | None = None) -> dict:
        r = {"length": end_long(mult * strength["length"]), "pitch": end_on_c(mult * strength["pitch"]),
             "level": strong_beats(mult * strength["level"], centroids)}
        if drop:
            r[drop] = lambda s, a: 0.0
        return r

    def exact_agents(r: dict, ms=models):
        rhythm = rhythm_agent(ms["length"], r["length"])
        counts = onset_counts(sample_rhythms(rhythm, ms["length"], RHYTHMS, SEED))
        return {"rhythm": rhythm, "pitch": pitch_agent(ms["pitch"], r["pitch"]),
                "loudness": loudness_agent(ms["level"], counts, r["level"])}

    baselines = exact_agents(rules(0.0))

    # practised main version (as in practise_agents.py) and the no-leash version
    main_exact = exact_agents(rules())
    pool = sample_rhythms(main_exact["rhythm"], models["length"], RHYTHMS, SEED)
    pool_starts = [note_starts(r) for r in pool]
    counts = onset_counts(pool)
    r_main = rules()
    learned = {"rhythm": SoftQLearner(rhythm_agent(models["length"], r_main["length"])),
               "pitch": SoftQLearner(pitch_agent(models["pitch"], r_main["pitch"])),
               "loudness": SoftQLearner(loudness_agent(models["level"], counts, r_main["level"]))}
    rng = random.Random(SEED + 2)
    r0, p0, l0 = models["length"].initial_state(), models["pitch"].initial_state(), models["level"].initial_state()
    budget = {
        "rhythm": practise(learned["rhythm"], main_exact["rhythm"], lambda k: (r0, 0),
                           lambda k, s, a, i: learned["rhythm"].moves(s, a)[0][1], [((r0, 0), 1)], lambda s: s[1], rng),
        "pitch": practise(learned["pitch"], main_exact["pitch"], lambda k: (p0, len(pool_starts[k % len(pool)])),
                          lambda k, s, a, i: (models["pitch"].next_state(s[0], a), s[1] - 1),
                          [((p0, n), c) for n, c in Counter(len(st) for st in pool_starts).items()], lambda s: -s[1], rng),
        "loudness": practise(learned["loudness"], main_exact["loudness"], lambda k: (l0, pool_starts[k % len(pool)][0]),
                             lambda k, s, a, i: (models["level"].next_state(s[0], a),
                                                 pool_starts[k % len(pool)][i + 1] if i + 1 < len(pool_starts[k % len(pool)]) else None),
                             [((l0, t), c) for t, c in Counter(st[0] for st in pool_starts).items()],
                             lambda s: 10 ** 6 if s[1] is None else s[1], rng)}
    print("practice pieces used:", budget, flush=True)

    no_leash = {"rhythm": NoLeashLearner(rhythm_agent(models["length"], r_main["length"])),
                "pitch": NoLeashLearner(pitch_agent(models["pitch"], r_main["pitch"])),
                "loudness": NoLeashLearner(loudness_agent(models["level"], {}, r_main["level"]))}
    rng = random.Random(SEED + 3)
    for _ in range(NO_LEASH_PIECES):
        tokens = no_leash["rhythm"].practise((r0, 0), lambda s, a, i: no_leash["rhythm"].moves(s, a)[0][1], rng)
        starts = note_starts(tokens) if tokens else []
        if starts:
            no_leash["pitch"].practise((p0, len(starts)), lambda s, a, i: (models["pitch"].next_state(s[0], a), s[1] - 1), rng)
            no_leash["loudness"].practise((l0, starts[0]), lambda s, a, i: (models["level"].next_state(s[0], a),
                                                                             starts[i + 1] if i + 1 < len(starts) else None), rng)

    memory2 = fit_chains(train, {"length": 2, "pitch": 1, "level": 1})
    conditions = {"baseline": (baselines, models, tempos),
                  "MDP main (practised)": (learned, models, tempos),
                  "MDP main (exact)": (main_exact, models, tempos),
                  **{f"MDP {m}x": (exact_agents(rules(m)), models, tempos) for m in (0.5, 2, 4)},
                  **{f"MDP without {label}": (exact_agents(rules(drop=c)), models, tempos)
                     for c, label in (("length", "long ending"), ("pitch", "ending on C"), ("level", "strong beats"))},
                  "no leash": (no_leash, models, tempos),
                  "baseline, rhythm memory 2 (added after the baseline)": (exact_agents(rules(0.0), memory2.models), memory2.models, memory2.tempos)}

    rng = random.Random(seed_for("real"))
    reference = {"tv": group_tv(train, test_dists, rng, len(test), REAL_GROUP_REPEATS),
                 "entropy": {s: entropy(test_dists[s]) for s in STATISTICS},
                 "features_test": compare_features(test_windows, test_windows),
                 "features_train": compare_features(train_windows, test_windows),
                 "rests_test": mean(map(rests_between_notes, test_windows)),
                 "rests_train": mean(map(rests_between_notes, train_windows)),
                 "copying": copying(test_windows, indexes), "diversity": diversity(test_windows, rng),
                 "n_test_windows": len(test_windows)}

    runs, examples, listening = {}, {}, {}
    for name, (agents, ms, tps) in conditions.items():
        t0 = time.time()
        rng = random.Random(seed_for("generate", name))
        pieces = [make_piece(agents["rhythm"], agents["pitch"], agents["loudness"], ms, tps, rng) for _ in range(ATTEMPTS)]
        done = [p for p in pieces if p]
        rng = random.Random(seed_for("measure", name))
        feats = compare_features(done, test_windows)
        dists = distributions(done)
        runs[name] = {"success_rate": len(done) / ATTEMPTS, "rules": rule_measures(done, centroids),
                      "tv": group_tv(done, test_dists, rng, GROUP_PIECES, GROUP_REPEATS),
                      "entropy": {s: entropy(dists[s]) for s in STATISTICS}, "features": feats,
                      "rests between notes": mean(map(rests_between_notes, done)),
                      "copying": copying(done[:COPY_SAMPLE], indexes), "diversity": diversity(done, rng),
                      "policy": policy_bits(done, agents, baselines, ms) if ms is models else None,
                      "seconds": round(time.time() - t0, 1)}
        examples[name] = done[:EXPORT.get(name, 0)]
        if name in LISTEN:
            listening[name] = [{"tokens": p.tokens, "pitches": p.pitches, "levels": p.levels}
                               for p in done[:LISTEN_PIECES]]
        print(f"{name:55s} {runs[name]['seconds']}s", flush=True)

    folder = OUT / "examples"
    for name, pieces in examples.items():
        if not pieces:
            continue
        stem = {"MDP main (practised)": "mdp", "MDP 4x": "mdp_4x", "no leash": "no_leash", "baseline": "baseline"}[name]
        for i, piece in enumerate(pieces, 1):
            try:
                write_midi(folder / f"{stem}_{i}.mid", piece.tempo, {"Melody": to_events(piece, vocabulary)})
            except PermissionError:                # the file is open in a player; keep the old copy
                print(f"could not overwrite {stem}_{i}.mid (file in use)", flush=True)

    (OUT / "listening_pieces.json").write_text(json.dumps(listening), encoding="utf-8")

    result = {"strengths": strength, "practice pieces used (main)": budget, "no-leash practice pieces": NO_LEASH_PIECES,
              "attempts": ATTEMPTS, "reference": reference, "runs": runs, "seconds": round(time.time() - started, 1)}
    (OUT / "results.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    text = summary(result)
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    print(text)


def summary(r: dict) -> str:
    runs, real = r["runs"], r["reference"]
    names = list(runs)
    short = {n: n.replace(" (added after the baseline)", "*") for n in names}
    head = "| | " + " | ".join(short[n] for n in names) + " |"
    rule = "|---|" + "---|" * len(names)
    lines = ["# MDP results", "", "Plan: `reports/mdp_plan.md`. Discussion: `reports/mdp_report.md`. "
             f"{r['attempts']} attempts per condition. * added after seeing the baseline's results.", "",
             f"Matched strengths: {', '.join(f'{k} {v:.4g}' for k, v in r['strengths'].items())}. "
             f"Practice pieces for the main version: {r['practice pieces used (main)']}; no leash: {r['no-leash practice pieces']}.", "",
             "## The rules", "", "| | target (training songs) | " + " | ".join(short[n] for n in names) + " |", "|---|---|" + "---|" * len(names)]
    for k, target in (("ends on C", "84%"), ("ends on a long note", "79%"), ("strong beats minus offbeats", "3.2")):
        fmt = (lambda v: f"{v:.0%}") if k != "strong beats minus offbeats" else (lambda v: f"{v:.1f}")
        lines.append(f"| {k} | {target} | " + " | ".join(fmt(runs[n]['rules'][k]) for n in names) + " |")
    lines += ["", "Targets: last notes of the training songs, and their loudness by beat (scripts/check_reward_rules.py).", "",
              "## How far each policy moved from the baseline (KL, bits per piece)", "", head, rule]
    for part in ("rhythm", "pitch", "loudness"):
        lines.append(f"| {part} | " + " | ".join(f"{runs[n]['policy']['bits per piece'][part]:.2f}" if runs[n]["policy"] else "-" for n in names) + " |")
    lines.append("| choices the baseline rules out | " + " | ".join(
        str(sum(runs[n]["policy"]["choices the baseline rules out"].values())) if runs[n]["policy"] else "-" for n in names) + " |")
    lines += ["", "## Distance from the test songs (total variation, 0 = identical)", "",
              "| statistic | real songs: mean (5th to 95th) | " + " | ".join(short[n] for n in names) + " |", "|---|---|" + "---|" * len(names)]
    for s in STATISTICS:
        t = real["tv"][s]
        lines.append(f"| {s} | {t['mean']:.3f} ({t['p5']:.3f} to {t['p95']:.3f}) | " + " | ".join(f"{runs[n]['tv'][s]['mean']:.3f}" for n in names) + " |")
    lines += ["", "## Entropy (bits)", "", "| statistic | test songs | " + " | ".join(short[n] for n in names) + " |", "|---|---|" + "---|" * len(names)]
    for s in STATISTICS:
        lines.append(f"| {s} | {real['entropy'][s]:.2f} | " + " | ".join(f"{runs[n]['entropy'][s]:.2f}" for n in names) + " |")
    lines += ["", "## Per piece: mean, and distance from real test excerpts (KS)", "",
              "| feature | test excerpts | training excerpts | " + " | ".join(short[n] for n in names) + " |", "|---|---|---|" + "---|" * len(names)]
    for f in real["features_test"]:
        if f == "silent sixteenths":
            continue
        lines.append(f"| {f} | {real['features_test'][f]['mean']:.1f} | {real['features_train'][f]['mean']:.1f} ({real['features_train'][f]['ks']:.2f}) | "
                     + " | ".join(f"{runs[n]['features'][f]['mean']:.1f} ({runs[n]['features'][f]['ks']:.2f})" for n in names) + " |")
    lines.append(f"| rests between notes (corrected silence) | {real['rests_test']:.1f} | {real['rests_train']:.1f} | "
                 + " | ".join(f"{runs[n]['rests between notes']:.1f}" for n in names) + " |")
    lines += ["", "## Copying from the training songs (longest copied run, share of the piece)", "",
              "| view | real test excerpts | " + " | ".join(short[n] for n in names) + " |", "|---|---|" + "---|" * len(names)]
    for v in VIEWS:
        lines.append(f"| {v} | {real['copying'][v]['longest_share']:.0%} | " + " | ".join(f"{runs[n]['copying'][v]['longest_share']:.0%}" for n in names) + " |")
    lines.append("| full copies (melody) | 0% | " + " | ".join(f"{runs[n]['copying']['melody']['full_copy']:.0%}" for n in names) + " |")
    lines += ["", "## Variety (4-gram overlap of random pairs, 0 = nothing shared)", "",
              "| | real test excerpts | " + " | ".join(short[n] for n in names) + " |", "|---|---|" + "---|" * len(names),
              "| unique pieces | " + f"{real['diversity']['unique_pieces']:.0%} | " + " | ".join(f"{runs[n]['diversity']['unique_pieces']:.0%}" for n in names) + " |"]
    for v in VIEWS:
        key = f"pair_overlap {v}"
        lines.append(f"| {v} | {real['diversity'][key]:.3f} | " + " | ".join(f"{runs[n]['diversity'][key]:.3f}" for n in names) + " |")
    lines += ["", "| | " + " | ".join(short[n] for n in names) + " |", rule,
              "| pieces finished | " + " | ".join(f"{runs[n]['success_rate']:.0%}" for n in names) + " |", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
