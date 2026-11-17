"""Build steps 1 and 2 of reports/listening_test_plan.md: choose the clips and turn them into MP3.

Clips (section 2 of the plan):
    real        one 8-bar excerpt per test song that ends at the first bar line after a phrase end
                (a note followed by at least 2 beats of silence, or the song's last note), drawn at random
    baseline    the first 10 of the baseline's 200 evaluation pieces (results/mdp/listening_pieces.json)
    MDP         the first 10 of the main version's 200 evaluation pieces (same file)
    Group 1 hears clips 1-5 of each condition, group 2 clips 6-10.
Extra clips, not part of the comparison: a practice clip (an excerpt from a training song, chosen by the
same rule), and two attention checks (one note repeated for 8 bars; a plain C major scale).

Every clip is played the same way: 90 beats per minute, the same loudness levels mapped to velocities,
each note held until the next note starts, silence before the first note trimmed to under one beat.
MuseScore 4 renders each MIDI file with its piano; ffmpeg cuts it one second after the last bar,
sets every clip to the same overall loudness (a fixed gain per clip, so the accents inside a clip stay)
and writes MP3.

Writes
    listening_test/public/clips/<id>.mp3  what listeners hear; the ids are random and say nothing
    listening_test/clips.json           which ids belong to group 1, group 2, practice and attention
                                        (read by listening_test/serve.py, never sent to the browser)
    results/listening/clip_key.json     the answer key: condition and source of every id (not for the page)
    results/listening/midi/<id>.mid     the MIDI behind each clip
    results/listening/stimuli.md        what was chosen, with the rule measures of each set

    python -I scripts/make_listening_clips.py
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from markov_music.mdp import ends_long, ends_on_c, rule_measures  # noqa: E402
from markov_music.musicxml_io import write_midi  # noqa: E402
from markov_music.pop909 import (WINDOW_BARS, WINDOW_MIN_NOTES, Melody, Vocabulary, draw_sample, load_pool,  # noqa: E402
                                 pool_checks, to_events, token_length)
from markov_music.theory import BAR  # noqa: E402
from run_baseline import seed_for, verify_pool  # noqa: E402

PIECES = ROOT / "results" / "mdp" / "listening_pieces.json"
PAGE = ROOT / "listening_test"
KEY = ROOT / "results" / "listening"
MUSESCORE = Path(os.environ.get("MUSESCORE", r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe"))
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

TEMPO = 90                     # beats per minute, for every clip
CLIPS = 10                     # per condition
PHRASE_GAP = 8                 # sixteenths of silence that end a phrase (2 beats)
BEAT = 4                       # sixteenths
TAIL_SECONDS = 1.0             # silence after the last bar
LOUDNESS = -23.0               # LUFS, every clip
SECONDS_PER_SIXTEENTH = 60 / TEMPO / 4


def phrase_excerpts(song) -> list[tuple[int, int, list[tuple]]]:
    """Every 8-bar excerpt (start bar line, end bar line, notes) that ends at the first bar line after a
    phrase end, with steady bars and at least WINDOW_MIN_NOTES notes."""
    notes, lines = song.notes, list(song.bar_lines)
    while lines[-1] < notes[-1][2]:        # the beat file can stop inside the final note: continue the bars
        lines.append(lines[-1] + BAR)
    found = []
    for j, note in enumerate(notes):
        nxt = notes[j + 1][1] if j + 1 < len(notes) else float("inf")
        if nxt - note[2] < PHRASE_GAP:
            continue
        ends = [k for k, line in enumerate(lines) if line >= note[2]]
        if not ends or ends[0] < WINDOW_BARS:
            continue
        k = ends[0]
        a, b = lines[k - WINDOW_BARS], lines[k]
        if b - a != WINDOW_BARS * BAR or nxt < b:      # unsteady bars, or another note before the bar line
            continue
        window = [n for n in notes if a <= n[1] < b]
        if len(window) >= WINDOW_MIN_NOTES and window[-1] is note:
            found.append((a, b, window))
    return found


def trimmed(melody: Melody, lead: int) -> Melody:
    """Silence before the first note cut to under one beat (the beat position inside the beat is kept)."""
    keep = lead % BEAT
    tokens = ([f"R{keep}"] if keep else []) + melody.tokens
    return Melody(melody.name, tokens, melody.pitches, melody.levels, TEMPO)


def real_clip(vocabulary: Vocabulary, song, excerpt) -> tuple[Melody, Melody, int]:
    """The clip as heard, the same excerpt with its full lead (for the rule measures), and its length."""
    a, b, window = excerpt
    m = vocabulary.encode(song, window, f"{song.id}_{a // BAR}")
    lead = window[0][1] - a
    heard = trimmed(m, lead)
    full = Melody(m.name, ([f"R{lead}"] if lead else []) + m.tokens, m.pitches, m.levels, TEMPO)
    length = (lead % BEAT) + (b - window[0][1])
    return heard, full, length


def attention_clips(vocabulary: Vocabulary) -> dict[str, Melody]:
    middle = min(range(len(vocabulary.centroids)), key=lambda i: abs(vocabulary.centroids[i]))
    bars = WINDOW_BARS * BAR // BEAT                   # quarter notes in 8 bars
    repeated = Melody("repeated note", ["N4"] * bars, [72] * bars, [middle] * bars, TEMPO)
    up_down = [60, 62, 64, 65, 67, 69, 71, 72, 71, 69, 67, 65, 64, 62]
    scale = (up_down * 3)[:bars - 4] + [60]            # up and down, ending on a whole-note C
    tokens = ["N4"] * (len(scale) - 1) + ["N16"]
    return {"repeated note": Melody("repeated note", repeated.tokens, repeated.pitches, repeated.levels, TEMPO),
            "C major scale": Melody("C major scale", tokens, scale, [middle] * len(scale), TEMPO)}


def render(midi: Path, mp3: Path, sixteenths: int, work: Path) -> dict:
    wav = work / (midi.stem + ".wav")
    subprocess.run([str(MUSESCORE), "-o", wav.as_posix(), midi.as_posix()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wav.exists():
        raise RuntimeError(f"MuseScore wrote nothing for {midi.name}")
    seconds = sixteenths * SECONDS_PER_SIXTEENTH + TAIL_SECONDS
    cut = f"atrim=0:{seconds:.3f},apad=whole_dur={seconds:.3f},afade=t=out:st={seconds - 0.15:.3f}:d=0.15"
    measured = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(wav), "-af", cut + ",ebur128",
                               "-f", "null", "-"], capture_output=True, text=True).stderr
    found = re.findall(r"I:\s+(-?[\d.]+) LUFS", measured)
    if not found:
        raise RuntimeError(f"could not measure {wav.name}")
    level = float(found[-1])
    gain = LOUDNESS - level
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav),
                    "-af", f"{cut},volume={gain:.2f}dB", "-ac", "1", "-c:a", "libmp3lame", "-q:a", "2", str(mp3)],
                   check=True)
    peak = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", str(mp3), "-af", "volumedetect", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    wav.unlink()
    return {"seconds": round(seconds, 2), "loudness before (LUFS)": level, "gain (dB)": round(gain, 2),
            "peak (dBFS)": float(re.findall(r"max_volume:\s+(-?[\d.]+) dB", peak)[-1])}


def main() -> None:
    songs = load_pool()
    verify_pool(pool_checks(songs))
    by_id = {s.id: s for s in songs}
    train_ids, _, test_ids = draw_sample(list(by_id))
    vocabulary = Vocabulary.fit([by_id[i] for i in train_ids])
    centroids = vocabulary.centroids
    generated = json.loads(PIECES.read_text(encoding="utf-8"))

    # --- choose ---------------------------------------------------------------------------------------
    rng = random.Random(seed_for("listening", "real"))
    clips, measures, sources = [], {}, {}
    real_full, candidates = [], {}
    for song_id in test_ids:
        options = phrase_excerpts(by_id[song_id])
        candidates[song_id] = len(options)
        if not options:
            raise RuntimeError(f"test song {song_id} has no excerpt that ends at a phrase end")
        excerpt = rng.choice(options)
        heard, full, length = real_clip(vocabulary, by_id[song_id], excerpt)
        clips.append(("real", heard, length, {"song": song_id, "bars": [excerpt[0] // BAR + 1, excerpt[1] // BAR]}))
        real_full.append(full)
    for condition, name in (("baseline", "baseline"), ("MDP", "MDP main (practised)")):
        pieces = [Melody(f"{condition}_{k}", p["tokens"], p["pitches"], p["levels"], TEMPO)
                  for k, p in enumerate(generated[name][:CLIPS], 1)]
        if len(pieces) < CLIPS:
            raise RuntimeError(f"only {len(pieces)} {condition} pieces in {PIECES.name}")
        for k, m in enumerate(pieces, 1):
            clips.append((condition, m, sum(map(token_length, m.tokens)), {"evaluation piece": k}))
        measures[condition] = rule_measures(pieces, centroids)
    measures["real"] = rule_measures(real_full, centroids)

    rng = random.Random(seed_for("listening", "practice"))
    practice_song = by_id[rng.choice(train_ids)]
    excerpt = rng.choice(phrase_excerpts(practice_song))
    heard, _, length = real_clip(vocabulary, practice_song, excerpt)
    extras = [("practice", heard, length, {"song": practice_song.id, "bars": [excerpt[0] // BAR + 1, excerpt[1] // BAR],
                                           "note": "a training song; not part of the comparison"})]
    for label, m in attention_clips(vocabulary).items():
        extras.append(("attention", m, sum(map(token_length, m.tokens)), {"clip": label}))

    # --- ids, groups, key -------------------------------------------------------------------------------
    rng = random.Random(seed_for("listening", "ids"))
    ids = set()
    while len(ids) < len(clips) + len(extras):
        ids.add(f"{rng.getrandbits(24):06x}")
    ids = sorted(ids)
    rng.shuffle(ids)
    key, page = {}, {"tempo": TEMPO, "groups": {"1": [], "2": []}, "practice": None, "attention": []}
    index = {"real": 0, "baseline": 0, "MDP": 0}
    for clip_id, (condition, m, length, source) in zip(ids, clips + extras):
        entry = {"condition": condition, "source": source, "notes": len(m.pitches), "sixteenths": length}
        if condition in index:
            index[condition] += 1
            entry["index"] = index[condition]
            entry["group"] = 1 if index[condition] <= CLIPS // 2 else 2
            entry["ends on C"] = bool(ends_on_c(m))
            entry["ends on a long note"] = bool(ends_long(m))
            page["groups"][str(entry["group"])].append(clip_id)
        elif condition == "practice":
            page["practice"] = clip_id
        else:
            page["attention"].append(clip_id)
        key[clip_id] = entry

    # --- render -----------------------------------------------------------------------------------------
    clip_dir, midi_dir, work = PAGE / "public" / "clips", KEY / "midi", KEY / "_render"
    for folder in (clip_dir, midi_dir, work):
        folder.mkdir(parents=True, exist_ok=True)
    for old in clip_dir.glob("*.mp3"):
        old.unlink()
    for clip_id, (condition, m, length, source) in zip(ids, clips + extras):
        midi = midi_dir / f"{clip_id}.mid"
        write_midi(midi, TEMPO, {"Piano": to_events(m, vocabulary)})
        key[clip_id]["audio"] = render(midi, clip_dir / f"{clip_id}.mp3", length, work)
        print(f"{clip_id} {condition:9s} {key[clip_id]['audio']}", flush=True)
    work.rmdir()

    page["seconds"] = {i: key[i]["audio"]["seconds"] for i in ids}
    (PAGE / "clips.json").write_text(json.dumps(page, indent=1), encoding="utf-8")
    (KEY / "clip_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    text = report(key, measures, candidates)
    (KEY / "stimuli.md").write_text(text, encoding="utf-8")
    print(text)


def report(key: dict, measures: dict, candidates: dict) -> str:
    lines = ["# Listening test clips", "",
             "Made by `scripts/make_listening_clips.py`, following `reports/listening_test_plan.md`.",
             f"All clips: {TEMPO} beats per minute, MuseScore 4 piano, {LOUDNESS:.0f} LUFS, "
             f"{TAIL_SECONDS:.0f} s of silence at the end.", "",
             "## Do the chosen clips represent their condition?", "",
             "| | Real (10 clips) | Baseline (10) | MDP (10) | Baseline, all 200 | MDP, all 200 |",
             "|---|---|---|---|---|---|"]
    full = json.loads((ROOT / "results" / "mdp" / "results.json").read_text(encoding="utf-8"))["runs"]
    every = {"baseline": full["baseline"]["rules"], "MDP": full["MDP main (practised)"]["rules"]}
    for rule, fmt in (("ends on C", "{:.0%}"), ("ends on a long note", "{:.0%}"), ("strong beats minus offbeats", "{:+.1f}")):
        row = [fmt.format(measures[c][rule]) for c in ("real", "baseline", "MDP")]
        row += [fmt.format(every[c][rule]) for c in ("baseline", "MDP")]
        lines.append(f"| {rule} | " + " | ".join(row) + " |")
    lines += ["", "Real clips end at a phrase end by construction, so they are expected to end well.", "",
              "## Phrase-end excerpts available per test song", "",
              "| Test song | Excerpts that end at a phrase end |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in candidates.items()]
    lines += ["", "## Clips", "",
              "| Id | Condition | Group | Source | Notes | Seconds | Gain (dB) | Peak (dBFS) | Ends on C | Ends long |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    order = {"real": 0, "baseline": 1, "MDP": 2, "practice": 3, "attention": 4}
    for i, e in sorted(key.items(), key=lambda kv: (order[kv[1]["condition"]], kv[1].get("index", 0))):
        src = ", ".join(f"{k} {v}" for k, v in e["source"].items() if k != "note")
        yes = {True: "yes", False: "no", None: ""}
        lines.append(f"| {i} | {e['condition']} {e.get('index', '')} | {e.get('group', '')} | {src} | {e['notes']} | "
                     f"{e['audio']['seconds']} | {e['audio']['gain (dB)']:+.1f} | {e['audio']['peak (dBFS)']:.1f} | "
                     f"{yes[e.get('ends on C')]} | {yes[e.get('ends on a long note')]} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
