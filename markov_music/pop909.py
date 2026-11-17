"""POP909: reading, the clean-up audited in reports/pop909_audit_rules.md, and the baseline's symbols.

A song becomes three sequences, one for each chain:
    tokens    note and rest lengths, e.g. "N2" = a note of 2 sixteenths, "R4" = a rest of 4
    pitches   one per note, moved to C major
    levels    one per note, loudness relative to the song's median, in equal-frequency levels

Everything learned from data (kept lengths, loudness levels) comes from the training songs only.
"""
from __future__ import annotations

import bisect
import statistics
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import mido
import numpy as np

from .musicxml_io import Event
from .theory import BAR, STEP_PC

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "pop909"

# Thresholds exactly as fixed in reports/pop909_audit_rules.md
TOL_S = 0.020                  # "within 20 ms"
GRID_MIN_SHARE = 0.95          # rule 9
BAR_STEADY_MIN = 0.90          # rule 10 (deviation 1)
VELOCITY_BINS = 39             # rule 13, as measured by the audit
REST_MIN = 4                   # deviation 2: a gap of at least one beat is a rest
SAMPLE_SEED = 20261106         # scope decision
N_TRAIN, N_VALIDATION, N_TEST = 80, 10, 10
LENGTH_COVERAGE = 0.99         # rare lengths
WINDOW_BARS = 8                # length of the pieces and of the real excerpts they are compared with
WINDOW_MIN_NOTES = 8           # an excerpt with fewer notes is an instrumental break, not melody


# --- reading ---------------------------------------------------------------

def read_index(data: Path = DATA) -> dict[str, tuple[int, int]]:
    """song id -> (beats per measure, quavers per beat), from index.xlsx (standard library only)."""
    m = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(data / "index.xlsx") as z:
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
    bar_lines: list[int] = field(default_factory=list)  # in sixteenths


def audit_song(folder: Path, metre: tuple[int, int]) -> Song:
    beats, bar_starts = read_beats(folder)
    gaps = [b - a for a, b in zip(bar_starts, bar_starts[1:])]
    song = Song(folder.name, metre, sum(g == 4 for g in gaps) / len(gaps) if gaps else 0.0)
    song.bar_lines = [4 * i for i in bar_starts]
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


# --- the songs used by the baseline ----------------------------------------

def passes_audit(song: Song) -> bool:
    """Rules 10, 9 and 15."""
    return (song.metre == (2, 2) and song.bar_steadiness >= BAR_STEADY_MIN
            and song.p16_onsets >= GRID_MIN_SHARE and len({n[4] for n in song.notes}) > 1)


def load_pool(data: Path = DATA) -> list[Song]:
    """Songs that pass the audit and whose only key segment is major (scope decision)."""
    index = read_index(data)
    pool = []
    for folder in sorted(p for p in data.iterdir() if p.is_dir()):
        keys = read_keys(folder)
        if len(keys) != 1 or not keys[0][2].endswith(":maj"):
            continue
        song = audit_song(folder, index[folder.name])
        if not song.excluded_by and passes_audit(song):
            pool.append(song)
    return pool


def draw_sample(song_ids: list[str]) -> tuple[list[str], list[str], list[str]]:
    """Training, validation and test songs, as fixed in the scope decision."""
    order = [str(s) for s in np.random.default_rng(SAMPLE_SEED).permutation(sorted(song_ids))]
    a, b, c = N_TRAIN, N_TRAIN + N_VALIDATION, N_TRAIN + N_VALIDATION + N_TEST
    return order[:a], order[a:b], order[b:c]


def tonic_shift(key: str) -> int:
    """Smallest move to C, from a label such as "Gb:maj"."""
    tonic = key.split(":")[0]
    pc = (STEP_PC[tonic[0]] + tonic.count("#") - tonic[1:].count("b")) % 12
    return -pc if pc <= 6 else 12 - pc


def note_tokens(notes: list[tuple]) -> list[str]:
    """Deviation 2: a note lasts until the next onset, unless a gap of at least one beat follows it.
    Then it keeps its sounding length and the gap becomes a rest."""
    tokens = []
    for cur, nxt in zip(notes, notes[1:]):
        gap = nxt[1] - cur[2]
        if gap >= REST_MIN:
            tokens += [f"N{cur[2] - cur[1]}", f"R{gap}"]
        else:
            tokens.append(f"N{nxt[1] - cur[1]}")
    tokens.append(f"N{notes[-1][2] - notes[-1][1]}")
    return tokens


def token_length(token: str) -> int:
    return int(token[1:])


def pool_checks(songs: list[Song]) -> dict:
    """The numbers recorded in deviation 2. Each song's last note is left out, since no gap follows it."""
    written, revised, rests_written, rests_revised = Counter(), Counter(), 0, 0
    for s in songs:
        for cur, nxt in zip(s.notes, s.notes[1:]):
            written[cur[2] - cur[1]] += 1
            rests_written += nxt[1] - cur[2] >= 1
        for token in note_tokens(s.notes)[:-1]:
            if token[0] == "N":
                revised[token_length(token)] += 1
            else:
                rests_revised += 1
    n = sum(written.values())
    return {"songs": len(songs), "notes": sum(len(s.notes) for s in songs),
            "as_written": {"most_common": written.most_common(1)[0][0], "share": written.most_common(1)[0][1] / n,
                           "rests_per_note": rests_written / n},
            "revised": {"most_common": revised.most_common(1)[0][0], "share": revised.most_common(1)[0][1] / n,
                        "rests_per_note": rests_revised / n}}


@dataclass
class Melody:
    """A melody as the chains see it. Rests appear only in `tokens`."""
    name: str
    tokens: list[str]
    pitches: list[int]
    levels: list[int]
    tempo: int = 90

    def sequence(self, chain: str) -> list:
        return {"length": self.tokens, "pitch": self.pitches, "level": self.levels}[chain]


def _song_median(song: Song) -> int:
    return round(statistics.median(n[4] for n in song.notes))


@dataclass
class Vocabulary:
    """Kept lengths and loudness levels, learned from the training songs."""
    tokens: list[str]                # kept lengths, most common first
    edges: np.ndarray                # loudness bin edges, relative to the song's median
    used: list[int]                  # bins that occur in training; level i is bin used[i]
    centroids: list[float]           # mean relative velocity of each level
    reference: int                   # median of the training songs' medians, for writing MIDI

    @classmethod
    def fit(cls, songs: list[Song]) -> "Vocabulary":
        counts = Counter(t for s in songs for t in note_tokens(s.notes))
        total, covered, kept = sum(counts.values()), 0, []
        for token, c in counts.most_common():
            if covered / total >= LENGTH_COVERAGE:
                break
            kept.append(token)
            covered += c
        relative = np.array([n[4] - _song_median(s) for s in songs for n in s.notes])
        edges = np.quantile(relative, np.linspace(0, 1, VELOCITY_BINS + 1)[1:-1])
        bins = np.searchsorted(edges, relative, side="right")
        used = sorted(int(b) for b in np.unique(bins))
        return cls(kept, edges, used, [float(relative[bins == b].mean()) for b in used],
                   round(statistics.median(_song_median(s) for s in songs)))

    def snap(self, token: str) -> str:
        """A rare length moves to the nearest kept length of the same kind; a tie goes to the shorter."""
        if token in self.tokens:
            return token
        same_kind = [t for t in self.tokens if t[0] == token[0]]
        return min(same_kind, key=lambda t: (abs(token_length(t) - token_length(token)), token_length(t)))

    def level(self, relative: int) -> int:
        raw = int(np.searchsorted(self.edges, relative, side="right"))
        return min(range(len(self.used)), key=lambda i: abs(self.used[i] - raw))

    def velocity(self, level: int) -> int:
        return int(np.clip(round(self.reference + self.centroids[level]), 1, 127))

    def encode(self, song: Song, notes: list[tuple] | None = None, name: str | None = None) -> Melody:
        notes = song.notes if notes is None else notes
        shift, median = tonic_shift(song.keys[0][2]), _song_median(song)
        return Melody(name or song.id, [self.snap(t) for t in note_tokens(notes)], [n[3] + shift for n in notes],
                      [self.level(n[4] - median) for n in notes], round(song.tempo_bpm))


def bar_windows(song: Song) -> list[list[tuple]]:
    """The song's notes cut at every 8th bar line. Excerpts with unsteady bars or too few notes are left out."""
    lines, windows = song.bar_lines, []
    for a, b in zip(lines[::WINDOW_BARS], lines[WINDOW_BARS::WINDOW_BARS]):
        notes = [n for n in song.notes if a <= n[1] < b]
        if b - a == WINDOW_BARS * BAR and len(notes) >= WINDOW_MIN_NOTES:
            windows.append(notes)
    return windows


def to_events(melody: Melody, vocabulary: Vocabulary) -> list[Event]:
    """The melody as MIDI-ready events, with loudness back on the velocity scale."""
    events, t, notes = [], 0, iter(zip(melody.pitches, melody.levels))
    for token in melody.tokens:
        if token[0] == "N":
            pitch, level = next(notes)
            events.append(Event(t, token_length(token), (pitch,), vocabulary.velocity(level)))
        t += token_length(token)
    return events
