"""Check the MDP's exact calculation on small examples worked out by hand, and that with no rule
points it is exactly the baseline."""
import math
import random
from collections import Counter

import pytest

from markov_music.baseline import fit_chains, generate_melody
from markov_music.generate import sample_constrained
from markov_music.mdp import (build_agents, generate_mdp_melody, loudness_agent, onset_counts, pitch_agent,
                              rhythm_agent, rhythm_only)
from markov_music.models import HigherOrderMC
from markov_music.pop909 import Melody, token_length
from markov_music.baseline import next_bar_line


def _melodies():
    rng = random.Random(1)
    out = []
    for k in range(6):
        tokens = [rng.choice(["N1", "N2", "N2", "N4", "N3"]) for _ in range(200)]
        n = len(tokens)
        tokens[50:50] = ["R4"]
        tokens[120:120] = ["R6"]
        out.append(Melody(str(k), tokens, [60 + rng.randrange(8) for _ in range(n)], [rng.randrange(5) for _ in range(n)], 90 + k))
    return out


def _sticky_chain():
    """C stays C with 0.9, D stays D with 0.9; the first note is C or D with 0.5 each."""
    return HigherOrderMC(1).fit([list("CC")] * 9 + [list("CD"), list("DC")] + [list("DD")] * 9, final=False)


def test_one_step_tilt():
    """Last note: p(C) = p(D) = 0.5 from the start; rule points ln 3 for ending on C -> 3 : 1."""
    model = HigherOrderMC(1).fit([list("C"), list("D")], final=False)
    agent = pitch_agent(model, lambda s, a: math.log(3) if s[1] == 1 and a == "C" else 0.0)
    assert agent.policy((model.initial_state(), 1)) == {"C": pytest.approx(0.75), "D": pytest.approx(0.25)}


def test_planning_ahead_two_notes_before_the_end():
    """weight(C, 1 left) = 0.9*3 + 0.1 = 2.8, weight(D, 1 left) = 0.1*3 + 0.9 = 1.2, so the first
    note is C with 0.5*2.8 / (0.5*2.8 + 0.5*1.2) = 0.7: the agent prepares the ending."""
    model = _sticky_chain()
    agent = pitch_agent(model, lambda s, a: math.log(3) if s[1] == 1 and a == "C" else 0.0)
    assert agent.weight((("C",), 1)) == pytest.approx(2.8)
    assert agent.weight((("D",), 1)) == pytest.approx(1.2)
    assert agent.policy((model.initial_state(), 2))["C"] == pytest.approx(0.7)
    assert pitch_agent(model).policy((model.initial_state(), 2))["C"] == pytest.approx(0.5)   # the baseline


def test_loudness_agent_takes_the_expected_future_when_the_rhythm_decides():
    """Levels 0/1 with p = 0.5 each. Level 1 on a note starting at 0 earns ln 2. A note at 4 is
    followed by a note at 0 or by the end, once each. weight(x, 0) = 0.5 + 0.5*2 = 1.5 and
    The agent cannot choose what the world does, so soft values are averaged:
    weight(x, 4) = exp((ln 1.5 + ln 1) / 2) = sqrt(1.5); at 0, level 1 has 2/3."""
    model = HigherOrderMC(1).fit([list("01"), list("10"), list("00"), list("11")], final=False)
    counts = {4: Counter({0: 1, None: 1}), 0: Counter({None: 1})}
    agent = loudness_agent(model, counts, lambda s, a: math.log(2) if s[1] == 0 and a == "1" else 0.0)
    assert agent.weight((("0",), 0)) == pytest.approx(1.5)
    assert agent.weight((("0",), 4)) == pytest.approx(1.5 ** 0.5)
    assert agent.policy((("1",), 0))["1"] == pytest.approx(2 / 3)


def test_onset_counts():
    counts = onset_counts([["N2", "R4", "N1", "N9"], ["N2", "N14"]])
    assert counts == {0: Counter({6: 1, 2: 1}), 6: Counter({7: 1}), 7: Counter({None: 1}), 2: Counter({None: 1})}


def test_policy_is_a_distribution_that_respects_the_bar_rule():
    model = HigherOrderMC(1).fit([m.tokens for m in _melodies()], final=False)
    agent = rhythm_agent(model, lambda s, a: 0.7 if a == "N4" else 0.0)
    state = (model.initial_state(), 0)
    for _ in range(40):
        pol = agent.policy(state)
        assert sum(pol.values()) == pytest.approx(1.0)
        assert all(state[1] + token_length(a) <= next_bar_line(state[1]) for a in pol)
        a = max(pol, key=pol.get)
        state = agent.moves(state, a)[0][1]
        if agent.is_end(state):
            break


@pytest.mark.parametrize("n", [1, 2])
def test_no_rule_points_gives_exactly_the_baseline_probabilities(n):
    """policy = p * beta(next) / beta(state), with beta from the baseline's own sampler."""
    model = HigherOrderMC(n).fit([m.tokens for m in _melodies()], final=False)
    memo = {}
    sample_constrained(model, 128, token_length, next_bar_line, random.Random(0), final=False, memo=memo)
    agent = rhythm_agent(model)
    checked = 0
    for (state, left), beta in memo.items():
        if left == 0 or beta == 0:
            continue
        t = 128 - left
        expected = {a: p * memo[(model.next_state(state, a), left - token_length(a))] / beta
                    for a, p in model.dist(state).items()
                    if t + token_length(a) <= next_bar_line(t) and (model.next_state(state, a), left - token_length(a)) in memo}
        expected = {a: v for a, v in expected.items() if v > 0}
        assert agent.policy((state, t)) == pytest.approx(expected, rel=1e-12)
        checked += 1
    assert checked > 50


@pytest.mark.parametrize("n", [1, 2])
def test_no_rule_points_gives_the_very_same_pieces(n):
    melodies = _melodies()
    chains = fit_chains(melodies, {"length": n, "pitch": n, "level": n})
    agents = build_agents(chains, onset_counts([rhythm_only(build_agents(chains, {}), random.Random(9)) for _ in range(50)]))
    for seed in range(40):
        a, _ = generate_melody(chains, random.Random(seed), "x")
        b, _ = generate_mdp_melody(agents, random.Random(seed), "x")
        assert (a.tokens, a.pitches, a.levels, a.tempo) == (b.tokens, b.pitches, b.levels, b.tempo)


# --- the rules ---------------------------------------------------------------------------------------

from markov_music.mdp import (beat_sign, end_long, end_on_c, expected, notes_done, policy_change,  # noqa: E402
                              rule_measures, strong_beats, strong_minus_offbeat, time_used)


def test_beat_sign():
    assert [beat_sign(t) for t in (0, 8, 16, 4, 12, 2, 1, 15)] == [1, 1, 1, 0, 0, -1, -1, -1]


def test_rules_pay_only_where_they_should():
    assert end_on_c(2.0)((("D",), 1), 72) == 2.0
    assert end_on_c(2.0)((("D",), 2), 72) == 0.0          # not the last note
    assert end_on_c(2.0)((("D",), 1), 74) == 0.0          # not a C
    assert end_long(1.5)((("N2",), 120), "N8") == 1.5      # a half note ending the piece
    assert end_long(1.5)((("N2",), 112), "N8") == 0.0      # long, but not the end
    assert end_long(1.5)((("N2",), 124), "N4") == 0.0      # the end, but short
    assert end_long(1.5)((("N2",), 120), "R8") == 0.0      # ending on a rest earns nothing
    centroids = [-10.0, 0.0, 10.0]
    assert strong_beats(0.5, centroids)((("1",), 16), 2) == 5.0     # loud on beat 1
    assert strong_beats(0.5, centroids)((("1",), 6), 0) == 5.0      # soft off the beat
    assert strong_beats(0.5, centroids)((("1",), 4), 2) == 0.0      # beat 2: no rule


def test_rule_measures_worked_example():
    centroids = [-4.0, 0.0, 6.0]
    a = Melody("a", ["N4", "N2", "N2", "N8"], [62, 64, 62, 72], [2, 0, 0, 2])     # starts 0, 4, 6, 8
    b = Melody("b", ["N8", "N4", "R4"], [60, 62], [1, 1])
    assert strong_minus_offbeat(a, centroids) == pytest.approx(6.0 - (-4.0))     # beats 1, 3 vs the offbeat at 6
    assert strong_minus_offbeat(b, centroids) is None                            # no offbeat note
    assert rule_measures([a, b], centroids) == {"ends on C": 0.5, "ends on a long note": 0.5,
                                                "strong beats minus offbeats": pytest.approx(10.0)}


def test_exact_chance_of_ending_on_c():
    """From test_planning_ahead...: first note C 0.7; then C with 0.9*3/2.8 after C and 0.1*3/1.2
    after D, so the piece ends on C with 0.7*2.7/2.8 + 0.3*0.3/1.2 = 0.75 (the baseline: 0.5)."""
    model = _sticky_chain()
    reward = lambda s, a: math.log(3) if s[1] == 1 and a == "C" else 0.0
    start = (model.initial_state(), 2)
    agent = pitch_agent(model, reward)
    assert expected(agent, start, notes_done, lambda s, a: s[1] == 1 and a == "C") == pytest.approx(0.75)
    assert expected(pitch_agent(model), start, notes_done, lambda s, a: s[1] == 1 and a == "C") == pytest.approx(0.5)
    assert policy_change(pitch_agent(model), pitch_agent(model), start, notes_done) == 0.0
    assert policy_change(agent, pitch_agent(model), start, notes_done) > 0


def test_exact_chance_agrees_with_sampling():
    model = HigherOrderMC(1).fit([m.tokens for m in _melodies()] + [["N2", "N8", "N4", "N8", "N2", "N2", "N8"] * 5],
                                 final=False)
    agent = rhythm_agent(model, end_long(1.0))
    start = (model.initial_state(), 0)
    exact = expected(agent, start, time_used, lambda s, a: end_long(1.0)(s, a) > 0)
    rng, hits = random.Random(3), 0
    for _ in range(4000):
        state = start
        while not agent.is_end(state):
            a = agent.choose(state, rng)
            state = agent.moves(state, a)[0][1]
        hits += token_length(a) >= 8 and a[0] == "N"
    assert hits / 4000 == pytest.approx(exact, abs=0.025)
    assert exact > expected(rhythm_agent(model), start, time_used, lambda s, a: end_long(1.0)(s, a) > 0)


# --- learning by practice ----------------------------------------------------------------------------

from markov_music.mdp import SoftQLearner, gap_to_exact, note_start  # noqa: E402


def test_practice_learns_to_prepare_the_ending():
    """The worked example above: practice must reach the exact 0.7 for a first C, and 2.8 / 1.2."""
    model = _sticky_chain()
    reward = lambda s, a: math.log(3) if s[1] == 1 and a == "C" else 0.0
    learner, rng = SoftQLearner(pitch_agent(model, reward)), random.Random(5)
    start = (model.initial_state(), 2)
    for _ in range(20000):
        learner.practise(start, lambda s, a, i: (model.next_state(s[0], a), s[1] - 1), rng)
    assert learner.policy(start)["C"] == pytest.approx(0.7, abs=0.01)
    assert math.exp(learner.value((("C",), 1))) == pytest.approx(2.8, abs=0.03)
    assert math.exp(learner.value((("D",), 1))) == pytest.approx(1.2, abs=0.03)


def test_practice_learns_the_loudness_example_with_the_rhythm_deciding():
    model = HigherOrderMC(1).fit([list("01"), list("10"), list("00"), list("11")], final=False)
    counts = {4: Counter({0: 1, None: 1}), 0: Counter({None: 1})}
    reward = lambda s, a: math.log(2) if s[1] == 0 and a == "1" else 0.0
    learner, rng = SoftQLearner(loudness_agent(model, counts, reward)), random.Random(6)
    for k in range(20000):
        starts = [4, 0] if k % 2 else [4]                   # the world: half the pieces have a second note at 0
        learner.practise((("0",), 4), lambda s, a, i: (model.next_state(s[0], a), starts[i + 1] if i + 1 < len(starts) else None), rng)
    assert learner.policy((("1",), 0))["1"] == pytest.approx(2 / 3, abs=0.01)
    assert math.exp(learner.value((("0",), 4))) == pytest.approx(1.5 ** 0.5, abs=0.01)


def test_practice_learns_the_bar_rule_look_ahead_and_matches_the_exact_answer():
    """With no rules, practice must find the baseline itself, including which lengths can still fill the bars."""
    model = HigherOrderMC(1).fit([m.tokens for m in _melodies()], final=False)
    exact, learner, rng = rhythm_agent(model, total=32), SoftQLearner(rhythm_agent(model, total=32)), random.Random(7)
    start = (model.initial_state(), 0)
    first = None
    for k in range(30000):
        learner.practise(start, lambda s, a, i: learner.agent.moves(s, a)[0][1], rng)
        if k == 100:
            first = gap_to_exact(learner, exact, [(start, 1)], time_used)["bits per choice"]
    final = gap_to_exact(learner, exact, [(start, 1)], time_used)["bits per choice"]
    assert final < 0.01 and final < first


# --- the data only as starting point (no leash) -------------------------------------------------------

from markov_music.mdp import NoLeashLearner  # noqa: E402


def test_without_the_leash_the_first_behaviour_is_the_data():
    model = _sticky_chain()
    learner = NoLeashLearner(pitch_agent(model, lambda s, a: 1.0 if s[1] == 1 and a == "C" else 0.0))
    assert learner.policy((("C",), 1)) == pytest.approx({"C": 0.9, "D": 0.1})


def test_without_the_leash_the_data_is_forgotten():
    """Rule points ln 3 for a final C. Learned: Q(last note, C) = ln 3, Q(last note, D) = 0 from either
    state, so the last note is C with 3/4 even after D, where the data says 0.1 (with the leash: 0.25).
    One note earlier both choices can still reach the points: Q = ln 3 for both, so 50/50 instead of 0.9/0.1."""
    model = _sticky_chain()
    reward = lambda s, a: math.log(3) if s[1] == 1 and a == "C" else 0.0
    learner, rng = NoLeashLearner(pitch_agent(model, reward)), random.Random(8)
    start = (model.initial_state(), 3)
    for _ in range(20000):
        learner.practise(start, lambda s, a, i: (model.next_state(s[0], a), s[1] - 1), rng)
    assert learner.policy((("D",), 1))["C"] == pytest.approx(0.75, abs=0.01)
    assert pitch_agent(model, reward).policy((("D",), 1))["C"] == pytest.approx(0.25)
    assert learner.policy((("C",), 2))["C"] == pytest.approx(0.5, abs=0.02)
