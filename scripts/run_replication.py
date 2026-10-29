"""Run the replication experiments and check them against the paper's claims.

Writes results/replication_results.json, results/summary.md and example pieces
(MusicXML + MIDI) to results/examples/.

    .venv/Scripts/python.exe scripts/run_replication.py [--attempts 200]
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
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from markov_music.analysis import analyse, load_style, piece_from_score  # noqa: E402
from markov_music.evaluate import copy_stats, features, tv_distance  # noqa: E402
from markov_music.generate import generate, train_style  # noqa: E402
from markov_music.musicxml_io import Event, read_musicxml, write_midi, write_musicxml  # noqa: E402

DATA = ROOT / "data" / "raw"
OUT = ROOT / "results"
STYLES = ["Burger", "Melted"]
# The paper's published outputs (superwillow.sourceforge.net demo table).
DEMOS = {"Burger": {"b2": "mixed", "b4": "mixed", "b5": "higher"},
         "Melted": {"m2": "mixed", "m4": "mixed", "m5": "higher"}}
VARIANTS = [("higher", {}), ("mixed", {}), ("mixed", {"min_count": 2})]
ORDERS = range(1, 11)
LENGTHS = (7, 8, 9, 10)          # bars; 8 is the main setting ("more or less eight measures")
EXPORT_ORDERS = (1, 2, 3, 5, 10)
COPY_SAMPLE = 100                # pieces per configuration used for copying statistics


def variant_name(kind: str, params: dict) -> str:
    return kind if not params else kind + "".join(f"_{k}{v}" for k, v in params.items())


def seed_for(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def export(piece, folder: Path, stem: str) -> None:
    parts = {"Lead": piece.lead,
             "Accompaniment": [Event(c.onset, c.duration, c.pitches) for c in piece.chords]}
    write_musicxml(folder / f"{stem}.xml", stem, piece.tempo, piece.n_bars, parts)
    write_midi(folder / f"{stem}.mid", piece.tempo, parts)


def representation_loss(pieces) -> dict:
    """Leaps larger than an octave cannot be written in the paper's melody alphabet."""
    leaps = total = 0
    for p in pieces:
        pitches = [e.pitches[-1] for e in p.lead]
        leaps += sum(abs(b - a) > 12 for a, b in zip(pitches, pitches[1:]))
        total += len(pitches) - 1
    return {"intervals": total, "leaps_over_octave": leaps}


def main(attempts: int) -> None:
    started = time.time()
    results: dict = {"attempts": attempts, "styles": {}}
    for style in STYLES:
        training = load_style(DATA / "superwillow_styles" / style, style)
        demos = {name: piece_from_score(read_musicxml(DATA / "superwillow_demos" / f"{name}.xml"), style)
                 for name in DEMOS[style]}
        res = results["styles"][style] = {
            "training_pieces": [p.name for p in training],
            "training_bars": [p.n_bars for p in training],
            "training_notes": sum(len(analyse(p).rhythm) for p in training),
            "representation": representation_loss(training),
            "features_training": features(training),
            "features_demos": features(list(demos.values())),
            "demos": {name: {"kind": DEMOS[style][name], "bars": d.n_bars, **copy_stats(d, training)}
                      for name, d in demos.items()},
            "runs": [],
        }
        for i, p in enumerate(training, 1):          # human pieces through the same renderer, for listening
            export(p, OUT / "examples" / style, f"{style}_human_{i}")
        for kind, params in VARIANTS:
            variant = variant_name(kind, params)
            for order in ORDERS:
                sm = train_style(training, kind, order, **params)
                n_states = {k: getattr(sm, k).n_states for k in ("chord_duration", "chord_progression", "rhythm", "melody")}
                for n_bars in LENGTHS:
                    rng = random.Random(seed_for(style, variant, order, n_bars))
                    ok, failed = [], Counter()
                    for i in range(attempts):
                        r = generate(sm, n_bars, rng, name=f"{style}_{variant}_L{order}_{i}")
                        if r.piece:
                            ok.append(r)
                        else:
                            failed[r.failed_step] += 1
                    run = {"variant": variant, "order": order, "bars": n_bars, "n_states": n_states,
                           "success_rate": len(ok) / attempts, "failed_steps": dict(failed)}
                    if n_bars == 8 and ok:
                        sample = ok[:COPY_SAMPLE]
                        stats = [copy_stats(r.piece, training) for r in sample]
                        run["copying"] = {k: mean(s[k] for s in stats) for k in stats[0]}
                        run["memory"] = {step: {"mean": mean(v for r in sample for v in r.memory[step]),
                                                "max": max(v for r in sample for v in r.memory[step])}
                                         for step in sample[0].memory}
                        run["features"] = features([r.piece for r in sample])
                        if order in EXPORT_ORDERS:
                            export(ok[0].piece, OUT / "examples" / style, f"{style}_{variant}_L{order}")
                    res["runs"].append(run)
                print(f"{style} {variant:16s} L={order:2d}  "
                      + "  ".join(f"{r['bars']}b:{r['success_rate']:.0%}" for r in res["runs"][-len(LENGTHS):]),
                      flush=True)
    results["seconds"] = round(time.time() - started, 1)
    OUT.mkdir(exist_ok=True)
    (OUT / "replication_results.json").write_text(json.dumps(results, indent=1))
    (OUT / "summary.md").write_text(summary(results), encoding="utf-8")
    print(f"done in {results['seconds']}s -> {OUT}")


def summary(results: dict) -> str:
    """Markdown tables of the main numbers (the report discusses them)."""
    lines = [f"# Replication results (attempts per setting: {results['attempts']})", ""]
    for style, res in results["styles"].items():
        runs = res["runs"]

        def get(variant, order, bars=8):
            return next(r for r in runs if r["variant"] == variant and r["order"] == order and r["bars"] == bars)

        variants = [variant_name(k, p) for k, p in VARIANTS]
        lines += [f"## {style}", "",
                  f"Training: {len(res['training_pieces'])} pieces, bars {res['training_bars']}, "
                  f"{res['training_notes']} melody notes; leaps over an octave: "
                  f"{res['representation']['leaps_over_octave']}/{res['representation']['intervals']}", "",
                  "### Success rate, 8 bars", "",
                  "| L | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
        for order in ORDERS:
            lines.append(f"| {order} | " + " | ".join(f"{get(v, order)['success_rate']:.0%}" for v in variants) + " |")
        lines += ["", "### Best success rate over lengths 7-10 bars", "",
                  "| L | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
        for order in ORDERS:
            cells = [max(get(v, order, b)["success_rate"] for b in LENGTHS) for v in variants]
            lines.append(f"| {order} | " + " | ".join(f"{c:.0%}" for c in cells) + " |")
        lines += ["", "### Failed step, 8 bars (counts)", "", "| L | " + " | ".join(variants) + " |",
                  "|---|" + "---|" * len(variants)]
        for order in ORDERS:
            lines.append(f"| {order} | " + " | ".join(
                ", ".join(f"{k} {n}" for k, n in get(v, order)["failed_steps"].items()) or "-" for v in variants) + " |")
        lines += ["", "### Copying from training (8 bars): mean longest copied run as share of the melody / share verbatim", "",
                  "| L | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
        for order in ORDERS:
            cells = []
            for v in variants:
                c = get(v, order).get("copying")
                cells.append(f"{c['copied_fraction']:.0%} / {c['verbatim']:.0%}" if c else "-")
            lines.append(f"| {order} | " + " | ".join(cells) + " |")
        lines += ["", "Paper's published pieces: " + "; ".join(
            f"{n} ({d['kind']}, {d['bars']} bars): longest run {d['copied_fraction']:.0%}, "
            f"4-gram overlap {d['4gram_overlap']:.0%}" for n, d in res["demos"].items()), "",
                  "### Memory actually used by the melody model (mean / max)", "",
                  "| L | " + " | ".join(variants) + " |", "|---|" + "---|" * len(variants)]
        for order in ORDERS:
            cells = []
            for v in variants:
                m = get(v, order).get("memory")
                cells.append(f"{m['melody']['mean']:.1f} / {m['melody']['max']}" if m else "-")
            lines.append(f"| {order} | " + " | ".join(cells) + " |")
        ft, fd = res["features_training"], res["features_demos"]
        lines += ["", "### Features: training vs paper's pieces vs ours (8 bars)", "",
                  "| set | notes/bar | ends on tonic | ends on I | mean abs interval | TV durations | TV numerals |",
                  "|---|---|---|---|---|---|---|"]

        def row(label, f):
            return (f"| {label} | {f['notes_per_bar']:.1f} | {f['ends_on_tonic']:.0%} | {f['ends_on_chord_I']:.0%} | "
                    f"{f['mean_abs_interval']:.1f} | {tv_distance(f['durations'], ft['durations']):.2f} | "
                    f"{tv_distance(f['numerals'], ft['numerals']):.2f} |")
        lines += [row("training", ft), row("paper (demos)", fd)]
        for v in ("higher", "mixed"):
            for order in (1, 2, 3, 5):
                f = get(v, order).get("features")
                if f:
                    lines.append(row(f"ours {v} L={order}", f))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=int, default=200)
    main(ap.parse_args().attempts)
