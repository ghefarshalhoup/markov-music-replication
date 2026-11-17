"""Check the POP909 baseline on small examples worked out by hand."""
import random

import mido
import numpy as np
import pytest

from markov_music.baseline import (CopyIndex, FixedPrior, WittenBell, diversity, fit_chains, generate_melody, ks_distance,
                                   next_bar_line, piece_features, steps, view)
from markov_music.evaluate import longest_common_run
from markov_music.generate import sample_constrained
from markov_music.models import HigherOrderMC
from markov_music.musicxml_io import Event, write_midi
from markov_music.pop909 import (Melody, Song, Vocabulary, bar_windows, draw_sample, note_tokens, to_events,
                                 token_length, tonic_shift)
from markov_music.theory import BAR


def note(onset, end, pitch=60, velocity=80):
    return (0.0, onset, end, pitch, velocity)


def song(notes, key="C:maj", tempo=90.0, bar_lines=()):
    return Song("001", (2, 2), 1.0, notes=notes, keys=[(0.0, 1.0, key)], tempo_bpm=tempo, bar_lines=list(bar_lines))


def test_length_runs_to_the_next_onset_unless_a_beat_or_more_of_silence_follows():
    notes = [note(0, 1), note(2, 3), note(8, 10)]          # gap of 1, then a gap of 5
    assert note_tokens(notes) == ["N2", "N1", "R5", "N2"]
    assert note_tokens([note(0, 2), note(5, 6)]) == ["N5", "N1"]          # gap of 3: not a rest
    assert note_tokens([note(0, 2), note(6, 7)]) == ["N2", "R4", "N1"]    # gap of exactly one beat: a rest


@pytest.mark.parametrize("key, shift", [("C:maj", 0), ("Db:maj", -1), ("Gb:maj", -6), ("F#:maj", -6),
                                        ("A:maj", 3), ("Bb:maj", 2), ("B:maj", 1), ("E:maj", -4)])
def test_songs_move_to_c_by_the_smallest_step(key, shift):
    assert tonic_shift(key) == shift


def test_sample_is_fixed_disjoint_and_sized_as_decided():
    ids = [f"{i:03d}" for i in range(335)]
    train, validation, test = draw_sample(ids)
    assert (len(train), len(validation), len(test)) == (80, 10, 10)
    assert len(set(train) | set(validation) | set(test)) == 100
    assert draw_sample(list(reversed(ids))) == (train, validation, test)      # order of the input does not matter


def _training_song():
    """Eighth notes with varied loudness, two kinds of rest and one rare note length."""
    notes, t = [], 0
    for i in range(100):
        notes.append(note(t, t + 2, velocity=60 + i % 8))
        t += 2
    notes.append(note(t, t + 1, velocity=60))
    t += 1 + 4
    notes.append(note(t, t + 1, velocity=60))
    t += 1 + 8
    notes.append(note(t, t + 3, velocity=60))
    return song(notes)


def test_rare_lengths_move_to_the_nearest_kept_length_of_the_same_kind():
    vocabulary = Vocabulary(["N2", "N4", "R4", "R8"], np.array([0.0]), [0, 1], [-1.0, 1.0], 80)
    assert vocabulary.snap("N2") == "N2"
    assert vocabulary.snap("N5") == "N4"
    assert vocabulary.snap("N3") == "N2"          # a tie goes to the shorter
    assert vocabulary.snap("R6") == "R4"
    assert vocabulary.snap("R30") == "R8"         # a rest never becomes a note


def test_vocabulary_keeps_99_percent_of_lengths_and_orders_loudness():
    s = _training_song()
    vocabulary = Vocabulary.fit([s])
    assert vocabulary.tokens[0] == "N2"
    counts = {t: note_tokens(s.notes).count(t) for t in set(note_tokens(s.notes))}
    assert sum(counts[t] for t in vocabulary.tokens) / sum(counts.values()) >= 0.99
    levels = [vocabulary.level(v) for v in range(-5, 6)]
    assert levels == sorted(levels)                            # louder is never a lower level
    assert vocabulary.centroids == sorted(vocabulary.centroids)
    melody = vocabulary.encode(s)
    assert len(melody.pitches) == len(melody.levels) == sum(t[0] == "N" for t in melody.tokens)


def test_encoding_moves_pitch_and_measures_loudness_from_the_songs_median():
    notes = [note(0, 2, 62, 70), note(2, 4, 64, 80), note(4, 6, 66, 90)]
    vocabulary = Vocabulary(["N2"], np.array([-5.0, 5.0]), [0, 1, 2], [-10.0, 0.0, 10.0], 100)
    melody = vocabulary.encode(song(notes, "D:maj"))
    assert melody.pitches == [60, 62, 64]
    assert melody.levels == [0, 1, 2]
    assert [e.velocity for e in to_events(melody, vocabulary)] == [90, 100, 110]


def test_witten_bell_worked_example():
    """Counts a=2, b=1 in a vocabulary of 3: T=2 kinds seen, N=3, so P(x) = (c(x) + 2/3) / 5."""
    wb = WittenBell([list("aab")], max_order=0, vocab_size=3)
    assert wb.probs([], "a")[0] == pytest.approx(8 / 15)
    assert wb.probs([], "b")[0] == pytest.approx(5 / 15)
    assert wb.probs([], "c")[0] == pytest.approx(2 / 15)


def test_witten_bell_is_a_distribution_for_every_memory():
    sequences = [list("abcabcabd"), list("bbaacd")]
    symbols = list("abcde")
    wb = WittenBell(sequences, max_order=3, vocab_size=len(symbols))
    fixed = FixedPrior(sequences, max_order=3, vocab_size=len(symbols), weight=10)
    for model in (wb, fixed):
        for context in (["a", "b", "c"], ["c", "c", "c"], ["<s>", "<s>", "a"], ["e", "e", "e"]):
            rows = np.array([model.probs(context, s) for s in symbols])
            assert rows.sum(axis=0) == pytest.approx([1.0] * 4)


def test_memory_helps_on_a_repeating_pattern():
    wb = WittenBell([list("abcd") * 50], max_order=2, vocab_size=5)
    bits = wb.bits(list("abcd") * 5)
    assert bits[0] > 19 * 1.9                      # about 2 bits per symbol without memory
    assert bits[2] < 0.25 * bits[0]


def test_a_no_memory_chain_is_just_the_frequencies():
    mc = HigherOrderMC(0).fit([list("aab")], final=False)
    assert mc.initial_state() == ()
    assert mc.dist(()) == {"a": pytest.approx(2 / 3), "b": pytest.approx(1 / 3)}
    assert mc.next_state((), "a") == ()


def _melodies():
    rng = random.Random(1)
    out = []
    for k in range(6):
        tokens = [rng.choice(["N1", "N2", "N2", "N4"]) for _ in range(200)]
        n = len(tokens)
        tokens[50:50] = ["R4"]
        out.append(Melody(str(k), tokens, [60 + rng.randrange(8) for _ in range(n)], [rng.randrange(5) for _ in range(n)], 90 + k))
    return out


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_generated_pieces_fill_the_bars_exactly(n):
    chains = fit_chains(_melodies(), {"length": n, "pitch": n, "level": n})
    rng = random.Random(n)
    for i in range(30):
        piece, failed = generate_melody(chains, rng, str(i))
        assert failed is None
        t = 0
        for token in piece.tokens:
            assert t + token_length(token) <= next_bar_line(t)      # stays inside its bar
            t += token_length(token)
        assert t == 8 * BAR
        assert len(piece.pitches) == len(piece.levels) == sum(x[0] == "N" for x in piece.tokens) > 0


def test_sharing_the_memo_changes_nothing():
    mc = HigherOrderMC(2).fit([list("abcabdabe") * 3, list("cabbae")], final=False)
    memo = {}
    for k in (3, 7, 5, 9, 7, 2):
        fresh = sample_constrained(mc, k, lambda _: 1, lambda t: k, random.Random(k), final=False)
        shared = sample_constrained(mc, k, lambda _: 1, lambda t: k, random.Random(k), final=False, memo=memo)
        assert shared == fresh


def test_copy_index_agrees_with_the_replications_measure():
    rng = random.Random(7)
    songs = [[rng.randrange(4) for _ in range(60)] for _ in range(5)]
    index = CopyIndex(songs)
    for _ in range(50):
        seq = [rng.randrange(5) for _ in range(rng.randrange(1, 40))]
        assert index.longest_run(seq) == max(longest_common_run(seq, s) for s in songs)


def test_a_copied_run_does_not_span_two_songs():
    index = CopyIndex([[1, 2, 3], [4, 5, 6]])
    assert index.longest_run([2, 3, 4, 5]) == 2


def test_melody_view_pairs_each_step_with_the_note_it_leads_to():
    m = Melody("x", ["N2", "R4", "N1", "N4"], [60, 62, 59], [0, 1, 2])
    assert steps(m.pitches) == [2, -3]
    assert view(m, "melody") == [(2, "N1"), (-3, "N4")]


def test_piece_features_worked_example():
    f = piece_features(Melody("x", ["N2", "R4", "N1", "N4"], [60, 62, 59], [0, 1, 3]))
    assert (f["notes"], f["distinct pitches"], f["pitch range"], f["rests"]) == (3, 3, 3, 1)
    assert f["mean step size"] == pytest.approx(2.5)
    assert f["silent sixteenths"] == 8 * BAR - 7
    assert (f["loudness range"], f["mean loudness step"]) == (3, pytest.approx(1.5))


def test_diversity_of_identical_and_of_different_pieces():
    same = [Melody(str(i), ["N2"] * 8, [60, 62, 64, 65, 67, 69, 71, 72], [0] * 8) for i in range(5)]
    d = diversity(same, random.Random(0), pairs=20)
    assert d["unique_pieces"] == pytest.approx(0.2)
    assert d["pair_overlap melody"] == pytest.approx(1.0)
    other = [Melody(str(i), ["N2"] * 8, [60 + 12 * i + j * (i + 1) for j in range(8)], [i] * 8) for i in range(5)]
    d = diversity(other, random.Random(0), pairs=20)
    assert d["unique_pieces"] == pytest.approx(1.0)
    assert d["pair_overlap pitch step"] == pytest.approx(0.0)


def test_ks_distance():
    assert ks_distance([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)
    assert ks_distance([1, 2], [3, 4]) == pytest.approx(1.0)
    assert ks_distance([1, 2, 3, 4], [3, 4, 5, 6]) == pytest.approx(0.5)


def test_excerpts_are_cut_at_every_eighth_bar_line():
    notes = [note(t, t + 2) for t in range(0, 8 * BAR, 2)] + [note(8 * BAR, 8 * BAR + 2)] + [note(t, t + 2) for t in range(16 * BAR, 24 * BAR, 2)]
    lines = [BAR * i for i in range(33)]
    windows = bar_windows(song(notes, bar_lines=lines))
    assert [len(w) for w in windows] == [64, 64]              # bars 9-16 have one note: not melody
    lines[1:] = [x + 1 for x in lines[1:]]                    # the first 8 bars are not 128 sixteenths long
    assert len(bar_windows(song(notes, bar_lines=lines))) == 1


def test_each_note_is_written_with_its_own_velocity(tmp_path):
    path = tmp_path / "piece.mid"
    write_midi(path, 90, {"Melody": [Event(0, 2, (60,), 50), Event(6, 4, (62,), 110), Event(10, 2, (64,))]})
    ons = [m for track in mido.MidiFile(path).tracks for m in track if m.type == "note_on"]
    assert [(m.note, m.velocity) for m in ons] == [(60, 50), (62, 110), (64, 90)]
