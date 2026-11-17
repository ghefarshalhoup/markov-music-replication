"""Phase 2: three agents on a leash (KL-control), as planned in reports/mdp_plan.md.

Each agent chooses one part of a note, in the baseline's order: rhythm, then pitch, then loudness.
Its score for a piece is

    rule points  -  how far its choices moved from the baseline's probabilities (KL divergence)

and the best behaviour for that score has a closed form (Todorov 2009; Fox et al. 2016):

    weight(s)     = sum_a  p(a|s) * exp(reward(s, a)) * future(s, a),   weight(end) = 1
    policy(a | s) = p(a|s) * exp(reward(s, a)) * future(s, a) / weight(s)
    future(s, a)  = exp(E[log weight(next state)])   (just weight(next) when the next state is fixed)

weight(s) is exp of the soft value V(s). It is worked out backward from the end of the piece.
With no rule points it is exactly the baseline's "duration left" sampler: weight is then the chance
of finishing the piece correctly, and the policy is the baseline's. The arithmetic is kept identical
to markov_music.generate, so with no rules the same seed gives the very same pieces.

What each agent sees (its state):
    rhythm    (last length or rest, time used so far)
    pitch     (last pitch, notes left)
    loudness  (last level, when this note starts)
The first part is the baseline chain's own state (n = 1); the second is the clock the baseline's
sampler already keeps, except for loudness, which also sees where its note falls in the bar.
For the loudness agent, when the next note starts is decided by the rhythm, so it is part of the
world: the exact calculation uses how often each next start follows in the rhythm agent's pieces,
and averages the soft values (log weights) over them, since the agent cannot choose the outcome.
"""
from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable

from .baseline import Chains, next_bar_line
from .models import END, HigherOrderMC
from .pop909 import WINDOW_BARS, Melody, token_length
from .theory import BAR

Reward = Callable[[tuple, object], float]


def no_reward(state, action) -> float:
    return 0.0


class Agent:
    """Exact best behaviour of one agent on the leash.

    data(state)          -> {action: baseline probability}
    moves(state, action) -> [(count, next state)], [] if the action is not allowed there.
                            One entry for a fixed outcome; several when the world decides (loudness).
    """

    def __init__(self, data: Callable, moves: Callable, is_end: Callable, reward: Reward = no_reward):
        self.data, self.moves, self.is_end, self.reward = data, moves, is_end, reward
        self.memo: dict = {}

    def _future(self, nexts) -> float:
        """exp(E[V(next)]): the average is taken over soft values, since the agent cannot choose what the
        world does (it is a geometric mean of weights). With one outcome this is just its weight."""
        if len(nexts) == 1:
            return self.weight(nexts[0][1])
        weights = [(c, self.weight(n)) for c, n in nexts]
        if any(w == 0 for _, w in weights):
            return 0.0
        return math.exp(sum(c * math.log(w) for c, w in weights) / sum(c for c, _ in weights))

    def scores(self, state) -> list[tuple[object, float]]:
        """Unnormalised policy: p(a|s) * exp(reward) * future(s, a)."""
        out = []
        for a, p in self.data(state).items():
            nexts = self.moves(state, a)
            if nexts:
                out.append((a, p * math.exp(self.reward(state, a)) * self._future(nexts)))
        return out

    def weight(self, state) -> float:
        if state not in self.memo:
            self.memo[state] = 1.0 if self.is_end(state) else sum(w for _, w in self.scores(state))
        return self.memo[state]

    def policy(self, state) -> dict:
        total = self.weight(state)
        return {a: w / total for a, w in self.scores(state) if w > 0} if total > 0 else {}

    def choose(self, state, rng: random.Random):
        options = self.scores(state)
        return rng.choices(options, weights=[w for _, w in options], k=1)[0][0]


def rhythm_agent(model: HigherOrderMC, reward: Reward = no_reward, total: int = WINDOW_BARS * BAR) -> Agent:
    """State (chain state, time used). A length or rest may not cross a bar line, as in the baseline."""
    def moves(state, a):
        chain, t = state
        t2 = t + token_length(a) if a != END else None
        return [(1, (model.next_state(chain, a), t2))] if t2 is not None and t2 <= next_bar_line(t) else []
    return Agent(lambda s: model.dist(s[0]), moves, lambda s: s[1] == total, reward)


def pitch_agent(model: HigherOrderMC, reward: Reward = no_reward) -> Agent:
    """State (chain state, notes left)."""
    def moves(state, a):
        return [(1, (model.next_state(state[0], a), state[1] - 1))] if a != END else []
    return Agent(lambda s: model.dist(s[0]), moves, lambda s: s[1] == 0, reward)


def onset_counts(rhythms: list[list[str]]) -> dict[int, Counter]:
    """How often each next note start (None: the piece ends) follows a note starting at t."""
    counts: dict[int, Counter] = defaultdict(Counter)
    for tokens in rhythms:
        starts = note_starts(tokens)
        for t, t2 in zip(starts, starts[1:] + [None]):
            counts[t][t2] += 1
    return dict(counts)


def loudness_agent(model: HigherOrderMC, counts: dict[int, Counter], reward: Reward = no_reward) -> Agent:
    """State (chain state, when this note starts); None as the start means the piece is over.
    A start never seen in the rhythm agent's pieces is treated as the last note."""
    def moves(state, a):
        if a == END:
            return []
        after = counts.get(state[1], {None: 1})
        nxt = model.next_state(state[0], a)
        return [(c, (nxt, t2)) for t2, c in after.items()]
    return Agent(lambda s: model.dist(s[0]), moves, lambda s: s[1] is None, reward)


def note_starts(tokens: list[str]) -> list[int]:
    t, out = 0, []
    for x in tokens:
        if x[0] == "N":
            out.append(t)
        t += token_length(x)
    return out


# --- the three rules (reports/mdp_plan.md, section 3) ------------------------------------------------

LONG = 8                       # a half note, in sixteenths


def beat_sign(t: int) -> int:
    """+1 on beats 1 and 3, -1 off the beat, 0 on beats 2 and 4."""
    p = t % BAR
    return 1 if p in (0, 8) else (0 if p % 4 == 0 else -1)


def end_long(strength: float, total: int = WINDOW_BARS * BAR) -> Reward:
    """Rhythm: points when the piece ends on a note of at least a half note."""
    def reward(state, a):
        return strength if a[0] == "N" and token_length(a) >= LONG and state[1] + token_length(a) == total else 0.0
    return reward


def end_on_c(strength: float) -> Reward:
    """Pitch: points when the last note is a C."""
    def reward(state, a):
        return strength if state[1] == 1 and a % 12 == 0 else 0.0
    return reward


def strong_beats(strength: float, centroids: list[float]) -> Reward:
    """Loudness: points for loudness (velocity above the song's median) on beats 1 and 3, and for
    softness off the beat."""
    def reward(state, a):
        return strength * beat_sign(state[1]) * centroids[a]
    return reward


def ends_on_c(m: Melody) -> bool:
    return m.pitches[-1] % 12 == 0


def ends_long(m: Melody) -> bool:
    return m.tokens[-1][0] == "N" and token_length(m.tokens[-1]) >= LONG


def strong_minus_offbeat(m: Melody, centroids: list[float]) -> float | None:
    """Mean velocity on beats 1 and 3 minus mean velocity off the beat; None without both."""
    strong, off = [], []
    for t, level in zip(note_starts(m.tokens), m.levels):
        (strong if beat_sign(t) == 1 else off if beat_sign(t) == -1 else []).append(centroids[level])
    return sum(strong) / len(strong) - sum(off) / len(off) if strong and off else None


def rule_measures(melodies: list[Melody], centroids: list[float]) -> dict[str, float]:
    diffs = [d for d in (strong_minus_offbeat(m, centroids) for m in melodies) if d is not None]
    return {"ends on C": sum(map(ends_on_c, melodies)) / len(melodies),
            "ends on a long note": sum(map(ends_long, melodies)) / len(melodies),
            "strong beats minus offbeats": sum(diffs) / len(diffs)}


# --- exact outcomes for the rhythm and pitch agents --------------------------------------------------

def visits(agent: Agent, start, progress: Callable) -> dict:
    """Chance that a piece passes through each state when the agent follows its exact best behaviour.
    progress(state) must grow with every step (time used, minus notes left, or note start)."""
    prob, pending = {start: 1.0}, {start}
    order = []
    while pending:
        s = min(pending, key=progress)
        pending.remove(s)
        order.append(s)
        if agent.is_end(s):
            continue
        for a, q in agent.policy(s).items():
            nexts = agent.moves(s, a)
            total = sum(c for c, _ in nexts)
            for c, nxt in nexts:
                prob[nxt] = prob.get(nxt, 0.0) + prob[s] * q * c / total
                pending.add(nxt)
    return {s: prob[s] for s in order}


def expected(agent: Agent, start, progress: Callable, feature: Callable) -> float:
    """Exact chance of a choice with the feature, e.g. ending on a long note."""
    return sum(p * sum(q for a, q in agent.policy(s).items() if feature(s, a))
               for s, p in visits(agent, start, progress).items() if not agent.is_end(s))


def kl(p: dict, q: dict) -> float:
    """KL(p || q) in bits."""
    return sum(v * math.log2(v / q[a]) for a, v in p.items() if v > 0)


def policy_change(agent: Agent, baseline: Agent, start, progress: Callable) -> float:
    """Exact bits per piece by which the agent's choices differ from the baseline's (KL)."""
    return sum(p * kl(agent.policy(s), baseline.policy(s))
               for s, p in visits(agent, start, progress).items() if not agent.is_end(s))


def time_used(state) -> int:
    return state[1]


def notes_done(state) -> int:
    return -state[1]


def note_start(state) -> int:
    return 10 ** 6 if state[1] is None else state[1]


# --- learning by practice ----------------------------------------------------------------------------

class SoftQLearner:
    """Learns an agent's best behaviour by practice: soft Q-learning (G-learning; Fox et al. 2016).

    The agent makes pieces with its current behaviour  pi(a|s) ~ p(a|s) * exp(Q(s, a)),  and after each
    choice moves Q(s, a) toward  reward + V(next),  where  V(s) = log sum_a p(a|s) exp(Q(s, a))  (0 at
    the end of the piece). Q starts at 0, so the first behaviour is the data's probabilities with no
    look-ahead. A choice that leads to a state with no way to finish gets Q = -inf: practice learns
    the bar rule's look-ahead (the baseline's "duration left") by itself. Step size 1 / visits^power.
    It uses the Agent's data, rules and allowed moves, but never its exact weights.
    """

    def __init__(self, agent: Agent, power: float = 0.7):
        self.agent, self.power = agent, power
        self.q: dict = {}
        self.visits: dict = {}
        self._options: dict = {}
        self.moves, self.is_end = agent.moves, agent.is_end      # so it can stand in for the Agent when generating

    def weight(self, state) -> float:
        return math.exp(self.value(state))

    def options(self, state) -> list[tuple]:
        if state not in self._options:
            self._options[state] = [(a, math.log(p), self.agent.reward(state, a)) for a, p in self.agent.data(state).items()
                                    if p > 0 and self.agent.moves(state, a)]
        return self._options[state]

    def _terms(self, state) -> list[tuple]:
        qs = self.q.get(state, {})
        return [(a, lp + qs.get(a, 0.0)) for a, lp, _ in self.options(state)]

    def value(self, state) -> float:
        if self.agent.is_end(state):
            return 0.0
        terms = [t for _, t in self._terms(state)]
        top = max(terms, default=-math.inf)
        return top if top == -math.inf else top + math.log(sum(math.exp(t - top) for t in terms))

    def policy(self, state) -> dict:
        v = self.value(state)
        return {} if v == -math.inf else {a: math.exp(t - v) for a, t in self._terms(state) if t > -math.inf}

    def choose(self, state, rng: random.Random):
        terms = [(a, t) for a, t in self._terms(state) if t > -math.inf]
        if not terms:
            return None
        top = max(t for _, t in terms)
        return rng.choices([a for a, _ in terms], weights=[math.exp(t - top) for _, t in terms], k=1)[0]

    def backup(self, state) -> float:
        """What the next state is worth in the update target."""
        return self.value(state)

    def update(self, state, action, nxt) -> None:
        reward = next(r for a, _, r in self.options(state) if a == action)
        target = reward + self.backup(nxt)
        n = self.visits[state, action] = self.visits.get((state, action), 0) + 1
        qs = self.q.setdefault(state, {})
        old = qs.get(action, 0.0)
        qs[action] = target if target == -math.inf or old == -math.inf else old + (target - old) / n ** self.power

    def practise(self, start, step: Callable, rng: random.Random) -> list | None:
        """One piece: its choices, or None if it got stuck. step(state, action, i) -> next state, from the world."""
        state, choices = start, []
        while not self.agent.is_end(state):
            a = self.choose(state, rng)
            if a is None:
                return None
            nxt = step(state, a, len(choices))
            self.update(state, a, nxt)
            state = nxt
            choices.append(a)
        return choices


class NoLeashLearner(SoftQLearner):
    """The comparison of reports/mdp_plan.md 4.5: the data only as the starting point.

    Q starts at log p(a|s), so the first behaviour  pi(a|s) ~ exp(Q(s, a))  is the data's. Learning then
    uses rule points only: the target is  reward + max_a' Q(next, a')  (ordinary Q-learning), with no cost
    for moving away from the data. Choices stay limited to those the training songs contain after the
    state, and are sampled the same way (softmax of Q).
    """

    def _terms(self, state) -> list[tuple]:
        qs = self.q.get(state, {})
        return [(a, qs.get(a, lp)) for a, lp, _ in self.options(state)]

    def backup(self, state) -> float:
        if self.agent.is_end(state):
            return 0.0
        return max((t for _, t in self._terms(state)), default=-math.inf)

    def update(self, state, action, nxt) -> None:
        if action not in self.q.get(state, {}):
            self.q.setdefault(state, {})[action] = next(lp for a, lp, _ in self.options(state) if a == action)
        super().update(state, action, nxt)


def gap_to_exact(learner: SoftQLearner, exact: Agent, starts: list[tuple], progress: Callable) -> dict:
    """How far practice is from the answer key: KL(exact || practised) in bits, per choice and per
    piece, over the states the exact behaviour visits. starts: [(start state, weight)]."""
    bits = steps = 0.0
    for start, w in starts:
        for s, p in visits(exact, start, progress).items():
            if not exact.is_end(s):
                learned = learner.policy(s)
                e = exact.policy(s)
                gap = math.inf if any(a not in learned for a in e) else kl(e, learned)
                bits += w * p * gap
                steps += w * p
    total = sum(w for _, w in starts)
    return {"bits per choice": bits / steps, "bits per piece": bits / total}


@dataclass
class Agents:
    rhythm: Agent
    pitch: Agent
    loudness: Agent
    models: dict[str, HigherOrderMC]
    tempos: list[int]


def build_agents(chains: Chains, counts: dict[int, Counter], rewards: dict[str, Reward] | None = None) -> Agents:
    rewards = rewards or {}
    m = chains.models
    return Agents(rhythm_agent(m["length"], rewards.get("length", no_reward)),
                  pitch_agent(m["pitch"], rewards.get("pitch", no_reward)),
                  loudness_agent(m["level"], counts, rewards.get("level", no_reward)),
                  m, chains.tempos)


def rhythm_only(agents: Agents, rng: random.Random) -> list[str] | None:
    state = (agents.models["length"].initial_state(), 0)
    if agents.rhythm.weight(state) == 0:
        return None
    tokens = []
    while not agents.rhythm.is_end(state):
        a = agents.rhythm.choose(state, rng)
        tokens.append(a)
        state = agents.rhythm.moves(state, a)[0][1]
    return tokens


def generate_mdp_melody(agents: Agents, rng: random.Random, name: str) -> tuple[Melody | None, str | None]:
    """A piece, or None and the agent that could not finish. Same order of random draws as the baseline."""
    tokens = rhythm_only(agents, rng)
    if tokens is None:
        return None, "length"
    n_notes = sum(t[0] == "N" for t in tokens)
    if n_notes == 0:
        return None, "length"

    state, pitches = (agents.models["pitch"].initial_state(), n_notes), []
    if agents.pitch.weight(state) == 0:
        return None, "pitch"
    while not agents.pitch.is_end(state):
        a = agents.pitch.choose(state, rng)
        pitches.append(a)
        state = agents.pitch.moves(state, a)[0][1]

    starts = note_starts(tokens)
    model = agents.models["level"]
    state, levels = (model.initial_state(), starts[0]), []
    if agents.loudness.weight(state) == 0:
        return None, "level"
    for i in range(n_notes):
        a = agents.loudness.choose(state, rng)
        levels.append(a)
        state = (model.next_state(state[0], a), starts[i + 1] if i + 1 < n_notes else None)
    return Melody(name, tokens, pitches, levels, rng.choice(agents.tempos)), None
