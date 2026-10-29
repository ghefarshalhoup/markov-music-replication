"""Audit POP909 against the decision rules fixed in reports/pop909_audit_rules.md.

Measurements only: no models. Writes results/pop909_audit/audit.json,
per_song.csv and summary.md.

    .venv/Scripts/python.exe -I scripts/audit_pop909.py
"""
from __future__ import annotations

import bisect
import csv
import json
import math
import statistics
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

import mido
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "pop909"
OUT = ROOT / "results" / "pop909_audit"

# Thresholds exactly as fixed in reports/pop909_audit_rules.md
TOL_S = 0.020                  # "within 20 ms"
GRID_MIN_SHARE = 0.95          # rule 9
BAR_STEADY_MIN = 0.90          # rule 10 (deviation 1)
REST_MIN_SHARE = 0.05          # rule 11
INFO_MIN_SHARE = 0.90          # rule 13
LEVELS = range(2, 65)          # rule 13
BETWEEN_SONG_MIN = 0.50        # rule 14
KEY_CHANGE_MAX_SHARE = 0.10    # rule 16
MIN_PART_BARS = 8              # rule 16, when songs are split
BAR = 16                       # sixteenths per 4/4 bar


# --- reading ---------------------------------------------------------------

def read_index() -> dict[str, tuple[int, int]]:
    """song id -> (beats per measure, quavers per beat), from index.xlsx (standard library only)."""
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(DATA / "index.xlsx") as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def value(cell):
        if cell.get("t") == "inlineStr":
            return "".join(t.text or "" for t in cell.iter(m + "t"))
        return cell.findtext(m + "v")

    rows = [[value(c) for c in r.findall(m + "c")] for r in sheet.iter(m + "row")]
    head = rows[0]
    i_id, i_b, i_q = head.index("song_id"), head.index("num_beats_per_measure"), head.index("num_quavers_per_beat")
    return {r[i_id]: (int(float(r[i_b])), int(float(r[i_q]))) for r in rows[1:]}


def read_beats(song: Path) -> tuple[np.ndarray, list[int]]:
    """Beat times in seconds, and indices of beats that start a 4-beat bar (third column)."""
    rows = [line.split() for line in (song / "beat_midi.txt").read_text().splitlines() if line.strip()]
    return np.array([float(r[0]) for r in rows]), [i for i, r in enumerate(rows) if float(r[2]) == 1.0]


def read_keys(song: Path) -> list[tuple[float, float, str]]:
    rows = [line.split() for line in (song / "key_audio.txt").read_text().splitlines() if line.strip()]
    return [(float(r[0]), float(r[1]), r[2]) for r in rows]


def _absolute(track):
    tick = 0
    for msg in track:
        tick += msg.time
        yield tick, msg


def read_melody(path: Path) -> list[tuple[float, float, int, int]] | None:
    """MELODY track as (onset s, end s, pitch, velocity), using the file's tempo map. None if absent."""
    mid = mido.MidiFile(path)
    changes = sorted((t, m.tempo) for tr in mid.tracks for t, m in _absolute(tr) if m.type == "set_tempo")
    if not changes or changes[0][0] > 0:
        changes.insert(0, (0, 500_000))
    starts, secs = [], []
    for i, (tick, tempo) in enumerate(changes):            # seconds at each tempo change
        if i == 0:
            secs.append(0.0)
        else:
            prev_tick, prev_tempo = changes[i - 1]
            secs.append(secs[-1] + (tick - prev_tick) * prev_tempo / 1e6 / mid.ticks_per_beat)
        starts.append(tick)

    def to_sec(tick):
        i = bisect.bisect_right(starts, tick) - 1
        return secs[i] + (tick - starts[i]) * changes[i][1] / 1e6 / mid.ticks_per_beat

    melody = next((tr for tr in mid.tracks if any(m.type == "track_name" and m.name.strip() == "MELODY" for m in tr)), None)
    if melody is None:
        return None
    notes, sounding = [], {}
    for tick, msg in _absolute(melody):
        if msg.type == "note_on" and msg.velocity > 0:
            sounding.setdefault(msg.note, []).append((tick, msg.velocity))
        elif msg.type in ("note_off", "note_on") and sounding.get(msg.note):
            start, velocity = sounding[msg.note].pop(0)
            notes.append((to_sec(start), to_sec(tick), msg.note, velocity))
    return sorted(notes)


# --- the beat grid ---------------------------------------------------------

def grid_position(t: float, beats: np.ndarray) -> tuple[float, float]:
    """Position of time t in sixteenths of the labelled beats, and the local sixteenth length in seconds.
    Before the first or after the last beat, the first or last beat interval is extrapolated."""
    i = int(np.clip(np.searchsorted(beats, t, side="right") - 1, 0, len(beats) - 2))
    beat = beats[i + 1] - beats[i]
    return 4 * i + 4 * (t - beats[i]) / beat, beat / 4


def off_grid(t: float, beats: np.ndarray, triplets: bool = False) -> float:
    """Distance in seconds to the nearest sixteenth (or, with triplets, sixteenth or triplet eighth)."""
    pos, sixteenth = grid_position(t, beats)
    d = abs(pos - round(pos)) * sixteenth
    if triplets:
        third = pos * 3 / 4                                  # position in triplet eighths
        d = min(d, abs(third - round(third)) * sixteenth * 4 / 3)
    return d


# --- one song --------------------------------------------------------------

@dataclass
class Song:
    id: str
    metre: tuple[int, int]
    bar_steadiness: float
    n_raw: int = 0
    p16_onsets: float = 0.0
    p16_ends: float = 0.0
    p_combined: float = 0.0
    simultaneous: int = 0
    overlapping: int = 0
    overlap_ms: list[float] = field(default_factory=list)
    collisions: int = 0
    lengthened: int = 0
    notes: list[tuple[float, int, int, int, int]] = field(default_factory=list)  # onset s, onset q, end q, pitch, velocity
    gaps16: list[float] = field(default_factory=list)   # unquantised gap to the next note, in sixteenths
    keys: list[tuple[float, float, str]] = field(default_factory=list)
    tempo_bpm: float = 0.0
    n_bars: float = 0.0
    excluded_by: str = ""


def audit_song(folder: Path, metre: tuple[int, int]) -> Song:
    beats, bar_starts = read_beats(folder)
    gaps = [b - a for a, b in zip(bar_starts, bar_starts[1:])]
    song = Song(folder.name, metre, sum(g == 4 for g in gaps) / len(gaps) if gaps else 0.0)
    song.keys = read_keys(folder)
    song.tempo_bpm = 60 / float(np.median(np.diff(beats)))
    song.n_bars = len(beats) / 4
    raw = read_melody(folder / f"{folder.name}.mid")
    if not raw:
        song.excluded_by = "no melody"
        return song
    song.n_raw = len(raw)
    song.p16_onsets = sum(off_grid(on, beats) <= TOL_S for on, *_ in raw) / len(raw)
    song.p16_ends = sum(off_grid(end, beats) <= TOL_S for _, end, *_ in raw) / len(raw)
    song.p_combined = sum(off_grid(on, beats, triplets=True) <= TOL_S for on, *_ in raw) / len(raw)

    # rule 12: notes starting within 20 ms of each other -> keep the highest
    kept: list[list] = []
    for on, end, pitch, vel in raw:
        if kept and on - kept[-1][0] <= TOL_S:
            song.simultaneous += 1
            if pitch > kept[-1][2]:
                kept[-1] = [on, end, pitch, vel]
            continue
        kept.append([on, end, pitch, vel])
    # rule 12: overlaps, then cut each note at the next onset
    for cur, nxt in zip(kept, kept[1:]):
        if cur[1] > nxt[0]:
            song.overlapping += 1
            song.overlap_ms.append((cur[1] - nxt[0]) * 1000)
            cur[1] = nxt[0]

    # quantise to sixteenths; notes landing on the same sixteenth keep the highest pitch
    quantised: list[list] = []
    for on, end, pitch, vel in kept:
        q_on, q_end = round(grid_position(on, beats)[0]), round(grid_position(end, beats)[0])
        if quantised and quantised[-1][1] == q_on:
            song.collisions += 1
            if pitch > quantised[-1][3]:
                quantised[-1] = [on, q_on, q_end, pitch, vel]
            continue
        quantised.append([on, q_on, q_end, pitch, vel])
    # notes shorter than half a sixteenth are kept with length one sixteenth (implementation note 1)
    for n in quantised:
        if n[2] <= n[1]:
            song.lengthened += 1
            n[2] = n[1] + 1
    for cur, nxt in zip(quantised, quantised[1:]):
        cur[2] = min(cur[2], nxt[1])
    song.notes = [tuple(n) for n in quantised]
    song.gaps16 = [grid_position(nxt[0], beats)[0] - grid_position(cur[1], beats)[0] for cur, nxt in zip(kept, kept[1:])]
    return song


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
