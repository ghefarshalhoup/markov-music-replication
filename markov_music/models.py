"""Sequence models from the paper: higher-order Markov chains and prediction suffix automata.

Both are used through the same small interface, so every generation step can run
on either:
    initial_state()          state before the first symbol
    dist(state)              {next symbol: probability}, END included when final states are used
    next_state(state, sym)   state after emitting sym
    memory(state)            how many previous symbols the state actually remembers

Higher-order MC (paper: "L-th order MC"): the state is the last L symbols. At the
start of a piece the state is padded with START, which is the paper's start state.

PSA (paper: "prediction suffix automaton", mixed order): the state is a variable-
length suffix of the history. LearnPSA (Ron, Singer & Tishby 1996) keeps a longer
context only when it predicts the next symbol differently from its shorter suffix.
"""
from __future__ import annotations

from collections import Counter, defaultdict

START, END = "<s>", "</s>"

State = tuple


def _normalise(counts: dict) -> dict:
    total = sum(counts.values())
    return {k: v / total for k, v in counts.items()}


class HigherOrderMC:
    kind = "higher"

    def __init__(self, order: int):
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.table: dict[State, dict] = {}

    def fit(self, sequences: list[list], final: bool = True) -> "HigherOrderMC":
        counts: dict[State, Counter] = defaultdict(Counter)
        for seq in sequences:
            padded = [START] * self.order + list(seq) + ([END] if final else [])
            for i in range(self.order, len(padded)):
                counts[tuple(padded[i - self.order:i])][padded[i]] += 1
        self.table = {ctx: _normalise(c) for ctx, c in counts.items()}
        return self

    def initial_state(self) -> State:
        return (START,) * self.order

    def dist(self, state: State) -> dict:
        return self.table.get(state, {})

    def next_state(self, state: State, symbol) -> State:
        return (state + (symbol,))[1:]

    def memory(self, state: State) -> int:
        return sum(s != START for s in state)

    @property
    def n_states(self) -> int:
        return len(self.table)


class PSA:
    """Prediction suffix automaton learned with LearnPSA.

    min_count:  a context must occur at least this often (the paper's "minimum
                probability of a sequence occurring", expressed as a count)
    ratio:      a context is kept if some next symbol is `ratio` times more likely
                after it than after its suffix (the paper's "factor")
    min_prob:   that next symbol must also have at least this probability
    two_sided:  also keep contexts that make a symbol `ratio` times *less* likely

    The defaults reproduce the paper's Figure 1 exactly (see tests); that example
    needs min_count=1, because the context "ede" occurs only once.
    """
    kind = "mixed"

    def __init__(self, max_order: int, min_count: int = 1, ratio: float = 1.05,
                 min_prob: float = 0.0, two_sided: bool = False):
        self.max_order = max_order
        self.min_count = min_count
        self.ratio = ratio
        self.min_prob = min_prob
        self.two_sided = two_sided
        self.tree: set[State] = set()        # contexts found by LearnPSA (+ their suffixes)
        self.states: set[State] = set()      # tree + missing prefixes = PSA state space
        self.table: dict[State, dict] = {}

    def fit(self, sequences: list[list], final: bool = True, start: bool = True) -> "PSA":
        follow: dict[State, Counter] = defaultdict(Counter)   # context -> next-symbol counts
        for seq in sequences:
            padded = ([START] if start else []) + list(seq) + ([END] if final else [])
            for i in range(1, len(padded)):
                if padded[i] == START:
                    continue
                for k in range(0, min(self.max_order, i) + 1):
                    follow[tuple(padded[i - k:i])][padded[i]] += 1
        prob = {ctx: _normalise(c) for ctx, c in follow.items()}
        count = {ctx: sum(c.values()) for ctx, c in follow.items()}
        alphabet = {s for ctx in follow for s in ctx}

        def significant(s: State) -> bool:
            here, shorter = prob[s], prob[s[1:]]
            for sym, p in here.items():
                if p < self.min_prob:
                    continue
                q = shorter[sym]
                if p / q > self.ratio or (self.two_sided and p / q < 1 / self.ratio):
                    return True
            # a symbol never seen after s but seen after its suffix can also differ
            return self.two_sided and any(sym not in here for sym in shorter)

        tree: set[State] = {()}
        frontier = [(s,) for s in alphabet if count.get((s,), 0) >= self.min_count]
        while frontier:
            s = frontier.pop()
            if significant(s):
                tree.update(s[i:] for i in range(len(s)))     # s and every suffix on its path
            if len(s) < self.max_order:
                frontier.extend((a,) + s for a in alphabet if count.get((a,) + s, 0) >= self.min_count)
        if start and (START,) in count:
            tree.add((START,))                                # the start state always exists
        self.tree = tree

        # PSA conversion: add missing prefixes so every state is reachable;
        # they inherit next-symbol probabilities from their longest suffix in the tree.
        states = set(tree)
        for s in tree:
            states.update(s[:i] for i in range(1, len(s)))
        self.states = states
        self.table = {}
        for s in states:
            source = next(s[i:] for i in range(len(s) + 1) if s[i:] in tree)
            self.table[s] = prob[source]
        return self

    def initial_state(self) -> State:
        return self.next_state((), START) if (START,) in self.states else ()

    def dist(self, state: State) -> dict:
        return self.table[state]

    def next_state(self, state: State, symbol) -> State:
        """Longest suffix of state + symbol that is a state of the automaton."""
        s = state + (symbol,)
        return next(s[i:] for i in range(len(s) + 1) if s[i:] in self.states)

    def memory(self, state: State) -> int:
        return sum(x != START for x in state)

    @property
    def n_states(self) -> int:
        return len(self.states)


def make_model(kind: str, order: int, **psa_params):
    if kind == "higher":
        return HigherOrderMC(order)
    if kind == "mixed":
        return PSA(order, **psa_params)
    raise ValueError(kind)
