"""Read and write the small subset of MusicXML used by SuperWillow, and write MIDI."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

import mido

from .theory import BAR, NOTE_TYPES, midi_pitch, split_writable


@dataclass
class Event:
    """One sounding event: a single note, a block chord, or a rest (no pitches)."""
    onset: int          # sixteenths from the start of the piece
    duration: int       # sixteenths
    pitches: tuple[int, ...]


@dataclass
class Score:
    name: str
    tempo: int
    key_fifths: int
    key_mode: str
    n_bars: int
    parts: dict[str, list[Event]] = field(default_factory=dict)


def read_musicxml(path: str | Path) -> Score:
    root = ET.parse(path).getroot()
    if root.tag != "score-partwise":
        raise ValueError(f"{path}: only partwise MusicXML is supported")
    names = {p.get("id"): (p.findtext("part-name") or p.get("id")).strip() for p in root.iter("score-part")}
    tempo = next((int(float(s.get("tempo"))) for s in root.iter("sound") if s.get("tempo")), 120)
    key = root.find(".//key")
    fifths = int(key.findtext("fifths")) if key is not None else 0
    mode = (key.findtext("mode") or "major") if key is not None else "major"

    score = Score(Path(path).stem, tempo, fifths, mode, 0)
    for part in root.iter("part"):
        events: list[Event] = []
        divisions, bar_start = 1, 0
        measures = part.findall("measure")
        for measure in measures:
            divs = measure.find("attributes/divisions")
            if divs is not None:
                divisions = int(divs.text)
            cursor = bar_start
            for el in measure:
                if el.tag in ("backup", "forward"):
                    shift = int(el.findtext("duration")) * 4 // divisions
                    cursor += -shift if el.tag == "backup" else shift
                if el.tag != "note":
                    continue
                dur = int(el.findtext("duration")) * 4 // divisions
                pitch_el = el.find("pitch")
                pitch = None if pitch_el is None else midi_pitch(
                    pitch_el.findtext("step"), int(float(pitch_el.findtext("alter") or 0)),
                    int(pitch_el.findtext("octave")))
                if el.find("chord") is not None:            # sounds with the previous note
                    prev = events[-1]
                    events[-1] = Event(prev.onset, prev.duration, prev.pitches + (pitch,))
                    continue
                tie_stop = any(t.get("type") == "stop" for t in el.findall("tie"))
                if tie_stop and events and events[-1].pitches == (pitch,):
                    prev = events[-1]                        # tied continuation: lengthen
                    events[-1] = Event(prev.onset, prev.duration + dur, prev.pitches)
                else:
                    events.append(Event(cursor, dur, () if pitch is None else (pitch,)))
                cursor += dur
            bar_start += BAR
        score.parts[names[part.get("id")]] = [Event(e.onset, e.duration, tuple(sorted(e.pitches))) for e in events]
        score.n_bars = max(score.n_bars, len(measures))
    return score


# --- writing ---------------------------------------------------------------

def _bar_pieces(onset: int, duration: int) -> list[tuple[int, int]]:
    """Split an event at bar lines and into writable note values -> [(onset, dur)]."""
    pieces, t, end = [], onset, onset + duration
    while t < end:
        bar_end = (t // BAR + 1) * BAR
        chunk = min(end, bar_end) - t
        for value in split_writable(chunk):
            pieces.append((t, value))
            t += value
    return pieces


def write_musicxml(path: str | Path, title: str, tempo: int, n_bars: int,
                   parts: dict[str, list[Event]]) -> None:
    score = ET.Element("score-partwise", version="3.1")
    ET.SubElement(ET.SubElement(score, "work"), "work-title").text = title
    part_list = ET.SubElement(score, "part-list")
    for i, name in enumerate(parts, 1):
        ET.SubElement(ET.SubElement(part_list, "score-part", id=f"P{i}"), "part-name").text = name

    for i, (name, events) in enumerate(parts.items(), 1):
        part = ET.SubElement(score, "part", id=f"P{i}")
        bars = [ET.SubElement(part, "measure", number=str(b + 1)) for b in range(n_bars)]
        attrs = ET.SubElement(bars[0], "attributes")
        ET.SubElement(attrs, "divisions").text = "4"
        key = ET.SubElement(attrs, "key")
        ET.SubElement(key, "fifths").text = "0"
        ET.SubElement(key, "mode").text = "major"
        time = ET.SubElement(attrs, "time")
        ET.SubElement(time, "beats").text = "4"
        ET.SubElement(time, "beat-type").text = "4"
        clef = ET.SubElement(attrs, "clef")
        ET.SubElement(clef, "sign").text = "G" if i == 1 else "F"
        ET.SubElement(clef, "line").text = "2" if i == 1 else "4"
        if i == 1:
            ET.SubElement(bars[0], "sound", tempo=str(tempo))

        for event in events:
            pieces = _bar_pieces(event.onset, event.duration)
            for k, (onset, dur) in enumerate(pieces):
                bar = bars[onset // BAR]
                for j, pitch in enumerate(event.pitches or (None,)):
                    note = ET.SubElement(bar, "note")
                    if j > 0:
                        ET.SubElement(note, "chord")
                    if pitch is None:
                        ET.SubElement(note, "rest")
                    else:
                        p = ET.SubElement(note, "pitch")
                        name = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"][pitch % 12]
                        alter = 1 if pitch % 12 in (1, 3, 6, 8, 10) else 0
                        ET.SubElement(p, "step").text = name
                        if alter:
                            ET.SubElement(p, "alter").text = str(alter)
                        ET.SubElement(p, "octave").text = str(pitch // 12 - 1)
                    ET.SubElement(note, "duration").text = str(dur)
                    if pitch is not None and len(pieces) > 1:
                        if k > 0:
                            ET.SubElement(note, "tie", type="stop")
                        if k < len(pieces) - 1:
                            ET.SubElement(note, "tie", type="start")
                    note_type, dots = NOTE_TYPES[dur]
                    ET.SubElement(note, "type").text = note_type
                    for _ in range(dots):
                        ET.SubElement(note, "dot")
    ET.indent(score)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write(b'<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 3.1 Partwise//EN" '
                 b'"http://www.musicxml.org/dtds/partwise.dtd">\n')
        fh.write(ET.tostring(score, encoding="utf-8"))


def write_midi(path: str | Path, tempo: int, parts: dict[str, list[Event]], velocity: int = 90) -> None:
    """Every note gets the same velocity: the paper's data marks every note forte."""
    ticks = 120  # per sixteenth (480 per quarter)
    mid = mido.MidiFile(ticks_per_beat=4 * ticks)
    for channel, (name, events) in enumerate(parts.items()):
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        if channel == 0:
            track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
        messages = []
        for e in events:
            for p in e.pitches:
                messages.append((e.onset * ticks, 1, mido.Message("note_on", note=p, velocity=velocity, channel=channel)))
                messages.append(((e.onset + e.duration) * ticks, 0, mido.Message("note_off", note=p, velocity=0, channel=channel)))
        now = 0
        for t, _, msg in sorted(messages, key=lambda m: (m[0], m[1])):
            track.append(msg.copy(time=t - now))
            now = t
        mid.tracks.append(track)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mid.save(path)
