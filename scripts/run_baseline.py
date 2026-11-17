"""Run the POP909 baseline and check it against the plan in reports/pop909_audit_rules.md.

Writes results/baseline/results.json, summary.md, songs.json and example pieces (MIDI) to
results/baseline/examples/.

    .venv/Scripts/python.exe -I scripts/run_baseline.py [--attempts 200]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import zlib
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from markov_music.baseline import (CHAINS, STATISTICS, VIEWS, CopyIndex, FixedPrior, WittenBell, compare_features,  # noqa: E402
                                   copying, distributions, diversity, entropy, fit_chains, generate_melody, group_tv, view)
from markov_music.musicxml_io import write_midi  # noqa: E402
from markov_music.pop909 import Vocabulary, bar_windows, draw_sample, load_pool, pool_checks, to_events  # noqa: E402

OUT = ROOT / "results" / "baseline"
MAX_ORDER = 8
COPY_SAMPLE = 100                # pieces per setting used for copying statistics
GROUP_PIECES = 100               # 100 pieces hold about as many notes as the 10 test songs
GROUP_REPEATS = 50
REAL_GROUP_REPEATS = 200
BOOTSTRAP = 2000
PRIOR_WEIGHTS = (1, 3, 10, 30, 100)
EXPORT = {"baseline": 5, "no memory": 3, "n=1": 2, "n=2": 2, "n=3": 2, "n=5": 2, "n=8": 2}
REAL_EXAMPLES = 5
STEP_STATISTICS = ("pitch step", "length pair", "loudness step")   # what a no-memory model cannot match by construction

# The numbers recorded in deviation 2; the data step has to give them again.
EXPECTED = {"songs": 335, "notes": 114187, "as_written_share": 45.7, "as_written_rests": 39.0,
            "revised_share": 48.8, "revised_rests": 3.4}


def seed_for(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def verify_pool(checks: dict) -> None:
    found = {"songs": checks["songs"], "notes": checks["notes"],
             "as_written_share": round(100 * checks["as_written"]["share"], 1),
             "as_written_rests": round(100 * checks["as_written"]["rests_per_note"], 1),
             "revised_share": round(100 * checks["revised"]["share"], 1),
             "revised_rests": round(100 * checks["revised"]["rests_per_note"], 1)}
    if found != EXPECTED:
        raise SystemExit(f"The data step does not reproduce the audit's numbers: {found} != {EXPECTED}")


def score_chain(chain: str, train, validation, test) -> dict:
    """Bits per symbol on held-out songs for every memory length; the validation songs choose n."""
    sequences = [m.sequence(chain) for m in train]
    vocab_size = len({x for s in sequences for x in s}) + 1      # one slot for anything never seen
    wb = WittenBell(sequences, MAX_ORDER, vocab_size)

    def per_song(melodies):
        return np.array([wb.bits(m.sequence(chain)) for m in melodies]), np.array([len(m.sequence(chain)) for m in melodies])

    val_bits, val_n = per_song(validation)
    test_bits, test_n = per_song(test)
    val_rate = val_bits.sum(axis=0) / val_n.sum()
    best = 1 + int(np.argmin(val_rate[1:]))

    gain = test_bits[:, best] - test_bits[:, 0]
    rng = np.random.default_rng(seed_for("bootstrap", chain))
    picks = rng.integers(0, len(test), (BOOTSTRAP, len(test)))
    resampled = gain[picks].sum(axis=1) / test_n[picks].sum(axis=1)

    # Sensitivity of the choice of n, on the validation songs only: to which songs were drawn, and to the smoothing.
    picks = rng.integers(0, len(validation), (BOOTSTRAP, len(validation)))
    drawn = Counter(1 + int(np.argmin((val_bits[p].sum(axis=0) / val_n[p].sum())[1:])) for p in picks)
    other = {}
    for weight in PRIOR_WEIGHTS:
        prior = FixedPrior(sequences, MAX_ORDER, vocab_size, weight)
        rate = sum(prior.bits(m.sequence(chain)) for m in validation) / val_n.sum()
        n = 1 + int(np.argmin(rate[1:]))
        other[weight] = {"best_n": n, "bits": float(rate[n])}
    return {"vocabulary": vocab_size - 1, "chosen_n": best,
            "n_when_validation_resampled": {n: c / BOOTSTRAP for n, c in sorted(drawn.items())},
            "other_smoothing": other,
            "uniform": float(np.log2(vocab_size)),
            "validation": [float(x) for x in val_rate],
            "test": [float(x) for x in test_bits.sum(axis=0) / test_n.sum()],
            "gain_vs_no_memory": float(gain.sum() / test_n.sum()),
            "gain_ci95": [float(x) for x in np.percentile(resampled, [2.5, 97.5])],
            "songs_improved": int((gain < 0).sum()),
            "test_total_bits": {"uniform": float(np.log2(vocab_size) * test_n.sum()),
                                "no memory": float(test_bits[:, 0].sum()),
                                "chosen": float(test_bits[:, best].sum())}}


def run_setting(name: str, orders: dict[str, int], train, test_dists, test_windows, indexes, attempts: int) -> tuple[dict, list]:
    rng = random.Random(seed_for("generate", name))
    chains = fit_chains(train, orders)
    pieces, failed = [], Counter()
    started = time.time()
    for i in range(attempts):
        piece, step = generate_melody(chains, rng, f"{name}_{i}")
        if piece:
            pieces.append(piece)
        else:
            failed[step] += 1
    out = {"orders": orders, "n_states": {c: chains.models[c].n_states for c in CHAINS},
           "success_rate": len(pieces) / attempts, "failed_steps": dict(failed),
           "seconds": round(time.time() - started, 1)}
    if pieces:
        rng = random.Random(seed_for("measure", name))
        dists = distributions(pieces)
        out.update(tv=group_tv(pieces, test_dists, rng, GROUP_PIECES, GROUP_REPEATS),
                   entropy={s: entropy(dists[s]) for s in STATISTICS},
                   features=compare_features(pieces, test_windows),
                   copying=copying(pieces[:COPY_SAMPLE], indexes),
                   diversity=diversity(pieces, rng))
    return out, pieces


def main(attempts: int) -> None:
    started = time.time()
    songs = load_pool()
    checks = pool_checks(songs)
    verify_pool(checks)
    by_id = {s.id: s for s in songs}
    train_ids, validation_ids, test_ids = draw_sample(list(by_id))
    vocabulary = Vocabulary.fit([by_id[i] for i in train_ids])

    def encode(ids):
        return [vocabulary.encode(by_id[i]) for i in ids]

    def windows(ids):
        return [vocabulary.encode(by_id[i], w, f"{i}_{k}") for i in ids for k, w in enumerate(bar_windows(by_id[i]))]

    train, validation, test = encode(train_ids), encode(validation_ids), encode(test_ids)
    train_windows, test_windows = windows(train_ids), windows(test_ids)
    print(f"pool {len(songs)} songs; train {sum(len(m.pitches) for m in train)} notes, "
          f"validation {sum(len(m.pitches) for m in validation)}, test {sum(len(m.pitches) for m in test)}; "
          f"{len(vocabulary.tokens)} lengths, {len(vocabulary.used)} loudness levels", flush=True)

    prediction = {c: score_chain(c, train, validation, test) for c in CHAINS}
    n_notes = sum(len(m.pitches) for m in test)
    joint = {k: sum(prediction[c]["test_total_bits"][k] for c in CHAINS) / n_notes for k in ("uniform", "no memory", "chosen")}
    orders = {c: prediction[c]["chosen_n"] for c in CHAINS}
    print("chosen memory:", orders, flush=True)

    test_dists = distributions(test)
    indexes = {name: CopyIndex([view(m, name) for m in train]) for name in VIEWS}
    rng = random.Random(seed_for("real"))
    reference = {
        "tv": group_tv(train, test_dists, rng, len(test), REAL_GROUP_REPEATS),
        "entropy": {s: entropy(test_dists[s]) for s in STATISTICS},
        "features_test": compare_features(test_windows, test_windows),
        "features_train": compare_features(train_windows, test_windows),
        "copying": copying(test_windows, indexes),
        "diversity": diversity(test_windows, rng),
        "n_test_windows": len(test_windows),
        "n_train_windows": len(train_windows),
    }

    settings = {"baseline": orders, "no memory": {c: 0 for c in CHAINS},
                **{f"n={n}": {c: n for c in CHAINS} for n in range(1, MAX_ORDER + 1)}}
    runs, examples = {}, {}
    for name, setting in settings.items():
        runs[name], pieces = run_setting(name, setting, train, test_dists, test_windows, indexes, attempts)
        examples[name] = pieces[:EXPORT.get(name, 0)]
        print(f"{name:10s} success {runs[name]['success_rate']:.0%}  {runs[name]['seconds']}s", flush=True)

    folder = OUT / "examples"
    for name, pieces in examples.items():
        for i, piece in enumerate(pieces, 1):
            stem = f"{name.replace(' ', '_').replace('=', '')}_{i}"
            write_midi(folder / f"{stem}.mid", piece.tempo, {"Melody": to_events(piece, vocabulary)})
    rng = random.Random(seed_for("real examples"))
    for i, piece in enumerate(rng.sample(test_windows, REAL_EXAMPLES), 1):
        write_midi(folder / f"real_test_{i}.mid", piece.tempo, {"Melody": to_events(piece, vocabulary)})

    results = {"attempts": attempts, "pool": checks, "train": train_ids, "validation": validation_ids, "test": test_ids,
               "lengths": vocabulary.tokens, "levels": len(vocabulary.used), "reference_velocity": vocabulary.reference,
               "notes": {"train": sum(len(m.pitches) for m in train), "validation": sum(len(m.pitches) for m in validation),
                         "test": n_notes},
               "prediction": prediction, "joint_bits_per_note": joint, "reference": reference, "runs": runs,
               "seconds": round(time.time() - started, 1)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    (OUT / "songs.json").write_text(json.dumps({"train": train_ids, "validation": validation_ids, "test": test_ids}, indent=1), encoding="utf-8")
    text = summary(results)
    (OUT / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"done in {results['seconds']}s -> {OUT}")


def checks_table(r: dict) -> list[str]:
    """The pass marks from the plan."""
    pred, base, none, real = r["prediction"], r["runs"]["baseline"], r["runs"]["no memory"], r["reference"]
    learned = all(p["test"][p["chosen_n"]] < p["test"][0] < p["uniform"] for p in pred.values())
    closer = {s: base["tv"][s]["mean"] < none["tv"][s]["mean"] for s in STEP_STATISTICS}
    within = {s: base["tv"][s]["mean"] <= real["tv"][s]["p95"] for s in STATISTICS}
    full = base["copying"]["melody"]["full_copy"]

    def rising(v):
        return ", ".join(f"{r['runs'][f'n={n}']['copying'][v]['longest_share']:.0%}" for n in range(1, MAX_ORDER + 1))
    return ["| Check | Result |", "|---|---|",
            f"| Reproduces the audit's numbers | yes ({r['pool']['songs']} songs, {r['pool']['notes']} notes) |",
            f"| Every chain beats no memory, which beats random | {'yes' if learned else 'NO'} |",
            "| ...and the 95% interval over test songs excludes zero | "
            + ", ".join(f"{c}: {'yes' if p['gain_ci95'][1] < 0 else 'NO'}" for c, p in pred.items()) + " |",
            "| Closer to the test songs than no memory (step statistics) | "
            + ", ".join(f"{s}: {'yes' if v else 'NO'}" for s, v in closer.items()) + " |",
            "| Within the range of real songs (95th percentile) | "
            + ", ".join(f"{s}: {'yes' if v else 'NO'}" for s, v in within.items()) + " |",
            f"| Pieces that fully copy a training melody | {full:.0%} |",
            f"| Longest copied run, baseline vs real test excerpts | {base['copying']['melody']['longest_share']:.0%} vs "
            f"{real['copying']['melody']['longest_share']:.0%} of the melody |",
            *[f"| Longest copied run for n = 1 to 8: {v} | {rising(v)} |" for v in VIEWS]]


def summary(r: dict) -> str:
    names = ["baseline", "no memory"] + [f"n={n}" for n in range(1, MAX_ORDER + 1)]
    runs, real, pred = r["runs"], r["reference"], r["prediction"]
    lines = ["# POP909 baseline results", "", "Plan: `reports/pop909_audit_rules.md`. Discussion: `reports/baseline_report.md`.", "",
             "## Checks", "", *checks_table(r), "",
             "## Data", "",
             f"- Songs: {len(r['train'])} training, {len(r['validation'])} validation, {len(r['test'])} test, from a pool of {r['pool']['songs']}.",
             f"- Notes: {r['notes']['train']} training, {r['notes']['validation']} validation, {r['notes']['test']} test.",
             f"- Lengths kept: {len(r['lengths'])} ({', '.join(r['lengths'])}).",
             f"- Loudness levels: {r['levels']}. Reference velocity for MIDI: {r['reference_velocity']}.",
             f"- Real 8-bar excerpts: {real['n_train_windows']} from training songs, {real['n_test_windows']} from test songs.", "",
             "## Predicting held-out songs (bits per symbol, lower is better)", "",
             "| n | " + " | ".join(f"{c}: validation | {c}: test" for c in CHAINS) + " |",
             "|---|" + "---|---|" * len(CHAINS)]
    for n in range(MAX_ORDER + 1):
        cells = []
        for c in CHAINS:
            mark = " **" if pred[c]["chosen_n"] == n else ""
            cells.append(f"{mark}{pred[c]['validation'][n]:.3f}{mark} | {pred[c]['test'][n]:.3f}")
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    lines += ["", "Bold: the n chosen on the validation songs. n = 0 is the no-memory reference.", "",
              "| chain | symbols | random guess | no memory | chosen n | at chosen n | gain (95% interval over songs) | test songs improved |",
              "|---|---|---|---|---|---|---|---|"]
    for c in CHAINS:
        p = pred[c]
        lines.append(f"| {c} | {p['vocabulary']} | {p['uniform']:.3f} | {p['test'][0]:.3f} | {p['chosen_n']} | {p['test'][p['chosen_n']]:.3f} | "
                     f"{p['gain_vs_no_memory']:.3f} ({p['gain_ci95'][0]:.3f} to {p['gain_ci95'][1]:.3f}) | {p['songs_improved']} of {len(r['test'])} |")
    j = r["joint_bits_per_note"]
    lines += ["", f"All three chains together, bits per note on the test songs: random {j['uniform']:.2f}, no memory {j['no memory']:.2f}, chosen {j['chosen']:.2f}.", "",
              "### How much the choice of n depends on chance and on the smoothing (validation songs only)", "",
              "Resampled: how often each n wins when the validation songs are redrawn. Weight w: a fixed trust in the shorter context, instead of Witten-Bell; cells give the best n and its bits.", "",
              "| chain | Witten-Bell | resampled | " + " | ".join(f"w={w}" for w in PRIOR_WEIGHTS) + " |",
              "|---|---|---|" + "---|" * len(PRIOR_WEIGHTS)]
    for c in CHAINS:
        p = pred[c]
        lines.append(f"| {c} | n={p['chosen_n']} ({p['validation'][p['chosen_n']]:.3f}) | "
                     + ", ".join(f"n={n}: {s:.0%}" for n, s in p["n_when_validation_resampled"].items()) + " | "
                     + " | ".join(f"n={p['other_smoothing'][w]['best_n']} ({p['other_smoothing'][w]['bits']:.3f})" for w in PRIOR_WEIGHTS) + " |")
    lines += ["", "## Distance from the test songs (total variation, 0 = identical)", "",
              "| statistic | real songs: mean (5th to 95th pct) | " + " | ".join(names) + " |",
              "|---|---|" + "---|" * len(names)]
    for s in STATISTICS:
        t = real["tv"][s]
        lines.append(f"| {s} | {t['mean']:.3f} ({t['p5']:.3f} to {t['p95']:.3f}) | "
                     + " | ".join(f"{runs[n]['tv'][s]['mean']:.3f}" if "tv" in runs[n] else "-" for n in names) + " |")
    lines += ["", "## Entropy (bits)", "", "| statistic | test songs | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for s in STATISTICS:
        lines.append(f"| {s} | {real['entropy'][s]:.2f} | " + " | ".join(f"{runs[n]['entropy'][s]:.2f}" if "entropy" in runs[n] else "-" for n in names) + " |")
    feats = list(real["features_test"])
    lines += ["", "## Per piece (8 bars): mean, and distance from real test excerpts (KS)", "",
              "| feature | test excerpts | training excerpts | " + " | ".join(names) + " |", "|---|---|---|" + "---|" * len(names)]
    for f in feats:
        lines.append(f"| {f} | {real['features_test'][f]['mean']:.1f} | {real['features_train'][f]['mean']:.1f} ({real['features_train'][f]['ks']:.2f}) | "
                     + " | ".join(f"{runs[n]['features'][f]['mean']:.1f} ({runs[n]['features'][f]['ks']:.2f})" if "features" in runs[n] else "-" for n in names) + " |")
    lines += ["", "## Generation and copying", "",
              "Copying compares each piece with the training songs. Real test excerpts are the natural level.", "",
              "| setting | success | melody: longest run, share | melody: 4-gram overlap | full copies | pitch steps: longest share | lengths: longest share | loudness: longest share |",
              "|---|---|---|---|---|---|---|---|"]

    def copy_row(label, success, c):
        return (f"| {label} | {success} | {c['melody']['longest_share']:.0%} | {c['melody']['gram_overlap']:.0%} | {c['melody']['full_copy']:.0%} | "
                f"{c['pitch step']['longest_share']:.0%} | {c['length']['longest_share']:.0%} | {c['loudness']['longest_share']:.0%} |")
    lines.append(copy_row("real test excerpts", "-", real["copying"]))
    for n in names:
        lines.append(copy_row(n, f"{runs[n]['success_rate']:.0%}", runs[n]["copying"]) if "copying" in runs[n]
                     else f"| {n} | {runs[n]['success_rate']:.0%} | - | - | - | - | - | - |")
    lines += ["", "## Variety between pieces", "",
              "Unique: share of pieces that differ from all others. Overlap: 4-grams shared by random pairs, 0 = nothing shared.", "",
              "| setting | unique pieces | unique melodies | overlap melody | overlap pitch steps | overlap lengths | overlap loudness |",
              "|---|---|---|---|---|---|---|"]

    def div_row(label, d):
        return (f"| {label} | {d['unique_pieces']:.0%} | {d['unique_melodies']:.0%} | {d['pair_overlap melody']:.3f} | "
                f"{d['pair_overlap pitch step']:.3f} | {d['pair_overlap length']:.3f} | {d['pair_overlap loudness']:.3f} |")
    lines.append(div_row("real test excerpts", real["diversity"]))
    lines += [div_row(n, runs[n]["diversity"]) for n in names if "diversity" in runs[n]]
    lines += ["", f"Size of each chain (contexts seen in training): " + "; ".join(
        f"{n}: " + ", ".join(f"{c} {runs[n]['n_states'][c]}" for c in CHAINS) for n in names), ""]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=int, default=200)
    main(ap.parse_args().attempts)
