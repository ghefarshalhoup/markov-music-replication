"""Audit POP909 against the decision rules fixed in reports/pop909_audit_rules.md.

Measurements only: no models. Writes results/pop909_audit/audit.json,
per_song.csv and summary.md.

    .venv/Scripts/python.exe -I scripts/audit_pop909.py
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from markov_music.pop909 import BAR_STEADY_MIN, DATA, GRID_MIN_SHARE, audit_song, read_index  # noqa: E402

OUT = ROOT / "results" / "pop909_audit"

# Thresholds exactly as fixed in reports/pop909_audit_rules.md
REST_MIN_SHARE = 0.05          # rule 11
INFO_MIN_SHARE = 0.90          # rule 13
LEVELS = range(2, 65)          # rule 13
BETWEEN_SONG_MIN = 0.50        # rule 14
KEY_CHANGE_MAX_SHARE = 0.10    # rule 16
MIN_PART_BARS = 8              # rule 16, when songs are split
BAR = 16                       # sixteenths per 4/4 bar


# --- statistics ------------------------------------------------------------

def entropy(values) -> float:
    counts = np.array(list(Counter(values).values()), dtype=float)
    p = counts / counts.sum()
    return float(-(p * np.log2(p)).sum())


def quantile_levels(values: np.ndarray, k: int) -> np.ndarray:
    """Equal-frequency binning into (at most) k levels; equal values always share a level."""
    edges = np.quantile(values, np.linspace(0, 1, k + 1)[1:-1])
    return np.searchsorted(edges, values, side="right")


def share(part: int, whole: int) -> float:
    return part / whole if whole else 0.0


def main() -> None:
    index = read_index()
    songs = [audit_song(f, index[f.name]) for f in sorted(p for p in DATA.iterdir() if p.is_dir())]
    flow = [("all songs", len(songs))]

    def step(name, keep):
        remaining = [s for s in songs if not s.excluded_by]
        for s in remaining:
            if not keep(s):
                s.excluded_by = name
        flow.append((f"after {name}", sum(not s.excluded_by for s in songs)))

    step("no melody", lambda s: True)
    step("metre (rule 10)", lambda s: s.metre == (2, 2) and s.bar_steadiness >= BAR_STEADY_MIN)
    grid_candidates = [s for s in songs if not s.excluded_by]
    step("timing grid (rule 9)", lambda s: s.p16_onsets >= GRID_MIN_SHARE)
    grid_failed = [s for s in grid_candidates if s.excluded_by == "timing grid (rule 9)"]
    step("constant velocity (rule 15)", lambda s: len({n[4] for n in s.notes}) > 1)

    remaining = [s for s in songs if not s.excluded_by]
    changing = [s for s in remaining if len(s.keys) > 1]
    key_change_share = share(len(changing), len(remaining))
    split = key_change_share > KEY_CHANGE_MAX_SHARE
    if not split:
        step("key changes (rule 16)", lambda s: len(s.keys) == 1)
        units = [(s.id, s.keys[0][2], s.notes) for s in songs if not s.excluded_by]
    else:                                                     # rule 16, second branch: split at key changes
        units = []
        for s in remaining:
            for i, (start, end, key) in enumerate(s.keys):
                part = [n for n in s.notes if start <= n[0] < end] if len(s.keys) > 1 else s.notes
                if part and (part[-1][2] - part[0][1]) / BAR >= MIN_PART_BARS:
                    units.append((f"{s.id}.{i}", key, part))
        flow.append(("units after splitting at key changes", len(units)))
    kept = [s for s in songs if not s.excluded_by]

    # rule 11: rests
    gaps = [nxt[1] - cur[2] for _, _, notes in units for cur, nxt in zip(notes, notes[1:])]
    rests = [g for g in gaps if g >= 1]
    rest_share = share(len(rests), len(gaps))
    raw_gaps = [g for s in kept for g in s.gaps16]
    # rule 12: size of the clean-up, on the kept songs
    n_raw = sum(s.n_raw for s in kept)
    # rule 14: between-song share of velocity variance
    vel_by_unit = [np.array([n[4] for n in notes], dtype=float) for _, _, notes in units]
    all_vel = np.concatenate(vel_by_unit)
    grand = all_vel.mean()
    eta2 = sum(len(v) * (v.mean() - grand) ** 2 for v in vel_by_unit) / ((all_vel - grand) ** 2).sum()
    relative = eta2 >= BETWEEN_SONG_MIN
    rep = (np.concatenate([v - round(statistics.median(v)) for v in vel_by_unit]) if relative else all_vel).astype(int)
    # rule 13: number of levels
    h_full = entropy(rep.tolist())
    info = {}
    for k in LEVELS:
        levels = quantile_levels(rep, k)
        info[k] = entropy(levels.tolist()) / h_full
    chosen_k = next((k for k in LEVELS if info[k] >= INFO_MIN_SHARE), None)
    rms = None
    if chosen_k:
        levels = quantile_levels(rep, chosen_k)
        centroids = {lv: rep[levels == lv].mean() for lv in np.unique(levels)}
        rms = float(np.sqrt(np.mean([(v - centroids[lv]) ** 2 for v, lv in zip(rep, levels)])))
        used_levels = len(centroids)
    # rule 15: low-dynamics songs that were kept
    stds = {s.id: float(np.std([n[4] for n in s.notes])) for s in kept}
    # rule 16: keys
    modes = Counter(key.split(":")[1] if ":" in key else key for _, key, _ in units)
    tonics = Counter(key.split(":")[0] for _, key, _ in units)

    # description
    durations = Counter(n[2] - n[1] for _, _, notes in units for n in notes)
    pitches = np.array([n[3] for _, _, notes in units for n in notes])
    notes_per_unit = [len(notes) for _, _, notes in units]
    bars_per_unit = [(notes[-1][2] - notes[0][1]) / BAR for _, _, notes in units]
    tempos = [s.tempo_bpm for s in kept]

    decisions = {
        "rule 9 timing grid": {
            "measured": f"{len(grid_failed)} of {len(grid_candidates)} songs below p16 = {GRID_MIN_SHARE}; "
                        f"median p16 = {statistics.median(s.p16_onsets for s in grid_candidates):.3f}",
            "decision": f"sixteenth grid; exclude {len(grid_failed)} songs "
                        f"({sum(s.p_combined >= GRID_MIN_SHARE for s in grid_failed)} of them would pass with triplets added)"},
        "rule 10 metre": {
            "measured": f"{sum(s.excluded_by == 'metre (rule 10)' for s in songs)} songs not simple duple or bars not steady",
            "decision": "keep simple duple metre with steady 4-beat bars (deviation 1)"},
        "rule 11 rests": {
            "measured": f"{rest_share:.1%} of melody notes are followed by a rest (threshold {REST_MIN_SHARE:.0%})",
            "decision": "rest symbol with its own duration" if rest_share >= REST_MIN_SHARE else "add gaps to the previous note"},
        "rule 12 clean-up": {
            "measured": f"simultaneous onsets {share(sum(s.simultaneous for s in kept), n_raw):.2%}, "
                        f"overlapping notes {share(sum(s.overlapping for s in kept), n_raw):.1%} "
                        f"(median overlap {statistics.median([x for s in kept for x in s.overlap_ms] or [0]):.0f} ms), "
                        f"same-sixteenth collisions {share(sum(s.collisions for s in kept), n_raw):.2%}, "
                        f"shorter than half a sixteenth (lengthened to one) {share(sum(s.lengthened for s in kept), n_raw):.2%}",
            "decision": "cut at the next onset; keep the highest of simultaneous notes (always applied)"},
        "rule 14 velocity reference": {
            "measured": f"between-song share of velocity variance = {eta2:.2f} (threshold {BETWEEN_SONG_MIN})",
            "decision": "relative to each song's median" if relative else "absolute MIDI velocity"},
        "rule 13 velocity levels": {
            "measured": f"H(V) = {h_full:.2f} bits; information kept: "
                        + ", ".join(f"k={k}: {info[k]:.0%}" for k in (4, 8, 12, 16, 24, 32, 48, 64)),
            "decision": f"{used_levels} levels (k = {chosen_k} bins requested; tied values merge), RMS error {rms:.2f} velocity units"
                        if chosen_k else "no k up to 64 reaches the threshold"},
        "rule 15 constant velocity": {
            "measured": f"{sum(s.excluded_by == 'constant velocity (rule 15)' for s in songs)} songs with one velocity value; "
                        f"{sum(v < 2 for v in stds.values())} kept songs have a standard deviation below 2",
            "decision": "exclude only the constant ones"},
        "rule 16 key changes": {
            "measured": f"{len(changing)} of {len(remaining)} songs ({key_change_share:.1%}) change key "
                        f"(threshold {KEY_CHANGE_MAX_SHARE:.0%}); modes {dict(modes)}",
            "decision": "split songs at key changes" if split else "exclude songs that change key"},
    }
    description = {
        "units": len(units),
        "melody notes": int(sum(notes_per_unit)),
        "notes per unit (median, min, max)": [statistics.median(notes_per_unit), min(notes_per_unit), max(notes_per_unit)],
        "bars per unit (median, min, max)": [statistics.median(bars_per_unit), min(bars_per_unit), max(bars_per_unit)],
        "tempo bpm (5th, 50th, 95th percentile)": [round(float(np.percentile(tempos, q)), 1) for q in (5, 50, 95)],
        "pitch (min, 1st pct, 99th pct, max)": [int(pitches.min()), int(np.percentile(pitches, 1)), int(np.percentile(pitches, 99)), int(pitches.max())],
        "distinct durations": len(durations),
        "durations in sixteenths (share)": {str(d): round(c / sum(durations.values()), 4) for d, c in durations.most_common(12)},
        "rest lengths in sixteenths (share)": {str(d): round(c / len(rests), 4) for d, c in Counter(rests).most_common(10)} if rests else {},
        "rests of at least one beat (share of rests)": share(sum(r >= 4 for r in rests), len(rests)),
        "rests of at least one bar (share of rests)": share(sum(r >= BAR for r in rests), len(rests)),
        "notes followed by a rest of at least one beat": share(sum(g >= 4 for g in gaps), len(gaps)),
        "unquantised gaps between notes, in sixteenths (share)": {
            label: round(share(sum(lo <= g < hi for g in raw_gaps), len(raw_gaps)), 4)
            for label, lo, hi in (("<0.1", -1e9, 0.1), ("0.1-0.5", 0.1, 0.5), ("0.5-1.5", 0.5, 1.5),
                                  ("1.5-4", 1.5, 4), (">=4", 4, 1e9))},
        "note ends within 20 ms of a sixteenth (median over songs)": statistics.median(s.p16_ends for s in kept),
        "key tonics": dict(tonics.most_common()),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(json.dumps({"flow": flow, "decisions": decisions, "description": description,
                                                "velocity_info_by_levels": info}, indent=1), encoding="utf-8")
    with open(OUT / "per_song.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["song", "beats_per_measure", "quavers_per_beat", "bar_steadiness", "melody_notes_raw", "p16_onsets",
                    "p16_ends", "p_with_triplets", "simultaneous", "overlapping", "collisions", "lengthened",
                    "notes_clean", "velocity_values", "velocity_std", "key_segments", "tempo_bpm", "bars", "excluded_by"])
        for s in songs:
            vel = [n[4] for n in s.notes]
            w.writerow([s.id, *s.metre, round(s.bar_steadiness, 3), s.n_raw, round(s.p16_onsets, 3), round(s.p16_ends, 3),
                        round(s.p_combined, 3), s.simultaneous, s.overlapping, s.collisions, s.lengthened, len(s.notes),
                        len(set(vel)), round(float(np.std(vel)), 2) if vel else "", len(s.keys), round(s.tempo_bpm, 1),
                        s.n_bars, s.excluded_by])
    lines = ["# POP909 audit results", "", "Rules: `reports/pop909_audit_rules.md`.", "", "## Songs kept after each filter", "",
             "| step | songs |", "|---|---|", *[f"| {name} | {n} |" for name, n in flow], "", "## Decisions", "",
             "| rule | measured | decision |", "|---|---|---|",
             *[f"| {rule} | {d['measured']} | {d['decision']} |" for rule, d in decisions.items()], "", "## Description", ""]
    lines += [f"- **{k}:** {v}" for k, v in description.items()]
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
