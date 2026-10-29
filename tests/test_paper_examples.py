"""Check the implementation against every worked example printed in the paper."""
import random
from fractions import Fraction

import pytest

from markov_music.analysis import ChordEvent, Piece, analyse, decode_melody, encode_melody
from markov_music.generate import sample_constrained
from markov_music.hmm import Emission, sample_posterior
from markov_music.models import END, START, PSA, HigherOrderMC
from markov_music.musicxml_io import Event
from markov_music.theory import classify_chord

# Paper, Figure 1: training sequences for the prediction suffix automaton.
FIG1 = [list("cdecdcdecd"), list("dedecdcdec")]

# Paper, Table 1: hidden (s) and observed (x) sequences for the HMM in Figure 2.
S1, X1 = list("cdecdcdecd"), "I I I V V V I I V V".split()
S2, X2 = list("dedecdcdec"), "I I I I V V V V I I".split()


def approx(value):
    return pytest.approx(float(value))


def test_figure2_transition_and_initial_probabilities():
    """a and pi in the paper (no final states in this example)."""
    mc = HigherOrderMC(1).fit([S1, S2], final=False)
    a = {"c": {"d": 1},
         "d": {"c": Fraction(2, 7), "e": Fraction(5, 7)},
         "e": {"c": Fraction(4, 5), "d": Fraction(1, 5)}}
    for state, row in a.items():
        assert mc.dist((state,)) == {k: approx(v) for k, v in row.items()}
    assert mc.dist((START,)) == {"c": approx(Fraction(1, 2)), "d": approx(Fraction(1, 2))}


def test_figure2_confusion_matrix():
    b = Emission().fit([S1, S2], [X1, X2])
    assert b.table["c"] == {"I": approx(Fraction(2, 7)), "V": approx(Fraction(5, 7))}
    assert b.table["d"] == {"I": approx(0.5), "V": approx(0.5)}
    assert b.table["e"] == {"I": approx(1)}


def test_figure1_prediction_suffix_automaton():
    psa = PSA(3).fit(FIG1, final=False, start=False)
    words = lambda states: {"".join(s) or "λ" for s in states}
    assert words(psa.states) == {"λ", "c", "d", "e", "cd", "dc", "ec", "de", "ed", "dcd", "cde", "ecd", "ede"}
    # "dc" and "ec" are not significant (c is always followed by d); they are only
    # added as prefixes so that dcd and ecd are reachable. "de" is in the tree
    # because it is the parent of cde and ede.
    assert words(psa.tree) == words(psa.states) - {"dc", "ec"}
    assert psa.dist(("d", "c")) == psa.dist(("c",)) == {"d": 1.0}
    edges = {("cd", "c"): "dc", ("cd", "e"): "cde", ("dc", "d"): "dcd", ("dcd", "e"): "cde",
             ("cde", "c"): "ec", ("ec", "d"): "ecd", ("ecd", "c"): "dc", ("ecd", "e"): "cde",
             ("ed", "e"): "ede", ("ede", "c"): "ec", ("e", "d"): "ed", ("d", "e"): "de",
             ("de", "c"): "ec", ("de", "d"): "ed", ("", "c"): "c"}
    for (src, sym), dst in edges.items():
        assert "".join(psa.next_state(tuple(src), sym)) == dst


def test_figure4_melodic_arc_encoding():
    """Lead f d f c g c over chords F, G, A (paper, Figure 4)."""
    F4, D5, F5, C5, G5 = 65, 74, 77, 72, 79
    lead = [Event(0, 4, (F4,)), Event(4, 4, (D5,)), Event(8, 4, (F5,)),
            Event(12, 4, (C5,)), Event(16, 8, (G5,)), Event(24, 8, (C5,))]
    chords = [ChordEvent(0, 12, classify_chord([41, 48]), (41, 48)),
              ChordEvent(12, 12, classify_chord([43, 50]), (43, 50)),
              ChordEvent(24, 8, classify_chord([45, 52]), (45, 52))]
    a = analyse(Piece("figure4", "test", 120, 2, lead, chords))
    assert a.melody_observed == ["IV", "IV", "IV", "V", "V", "VI"]
    # The paper prints {=4, +2, +4, -1, +3, -1}. Its fifth symbol contradicts its own
    # definition: g is the 5th degree of C major, so the symbol is "+5".
    assert a.melody_hidden == ["=4", "+2", "+4", "-1", "+5", "-1"]


def test_melody_decoding_inverts_encoding_for_leaps_up_to_an_octave():
    pitches = [72, 74, 71, 79, 67, 67, 76, 65]
    assert decode_melody(encode_melody(pitches), pitches[0]) == pitches


def test_chord_classification_handles_inversions():
    assert str(classify_chord([64, 69, 72])) == "A:min"     # E4 A4 C5
    assert classify_chord([64, 69, 72]).numeral == "VI"
    assert str(classify_chord([62, 67, 71])) == "G"          # D4 G4 B4
    assert str(classify_chord([62, 69, 76])) == "D:sus2"     # bass decides Dsus2 vs Asus4


def test_duration_left_sampling_hits_the_total_and_respects_limits():
    mc = HigherOrderMC(1).fit([[4, 4, 8], [2, 2, 4, 8], [8, 8]])
    rng = random.Random(1)
    for _ in range(50):
        symbols, _ = sample_constrained(mc, 32, lambda d: d, lambda t: (t // 16 + 1) * 16, rng)
        assert sum(symbols) == 32
        onsets = [sum(symbols[:i]) for i in range(len(symbols))]
        assert all(t // 16 == (t + d - 1) // 16 for t, d in zip(onsets, symbols))   # no bar crossing
    assert sample_constrained(mc, 5, lambda d: d, lambda t: 5, rng) is None          # impossible total


def test_posterior_sampling_only_returns_possible_melodies():
    mc = HigherOrderMC(1).fit([S1, S2])
    b = Emission().fit([S1, S2], [X1, X2])
    rng = random.Random(0)
    for _ in range(50):
        hidden, _ = sample_posterior(mc, b, ["I", "I", "V", "V"], rng)
        assert all(b.prob(h, o) > 0 for h, o in zip(hidden, ["I", "I", "V", "V"]))
        state = mc.initial_state()
        for h in hidden:
            assert mc.dist(state)[h] > 0
            state = mc.next_state(state, h)
        assert mc.dist(state).get(END, 0) > 0
