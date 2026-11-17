# MDP plan (Phase 2)

Written 2026-11-09; all decisions taken 2026-11-17 (section 8). Building has started.

Sources:
- the candidate-rule numbers come from `scripts/check_reward_rules.py`, which reads the 80 training songs only and writes `results/reward_rules/checks.json`;
- the baseline numbers come from `reports/baseline_report.md`.

## In short

- **What it does.** The MDP chooses notes the way the baseline does, but it also earns points for a few musical qualities and learns to plan ahead for them. A "leash" keeps its choices close to the baseline's probabilities.
- **Rules tested.** We checked candidate rules on the training songs.
  - Three pass: **end on C**, **end on a long note** and **louder on strong beats**.
  - Several are not needed, because the baseline already behaves like real songs.
  - **Range** cannot be rewarded unless the agent is told one more fact: the first note.
  - The **pause** gap was mostly a problem with how we measured silence.
- **Rule strength.** Each rule is tuned so that pieces follow it about as often as real songs do. Stronger settings are also run, to show what pushing harder costs.
- **Still open.** Section 8 lists what you still need to decide.

## 1. Research questions

1. Does rewarding a musical quality improve it over the baseline, and by how much?
2. What does that cost in resemblance to real music, in variety and in originality (copying)?
3. How does the note-selection policy change? Which choices gain or lose probability, and where in the piece?
4. Do listeners hear a difference? This needs a listening test, planned later.

## 2. Decisions

| # | Question | Choice | Status |
|---|---|---|---|
| 1 | How the data probabilities guide the AI | Main version: a leash inside the reward. Comparison: data as starting point only | Decided 2026-11-09 |
| 2 | What earns points | End on C, end on a long note, louder on strong beats (section 3); range only as an optional extra | Decided 2026-11-17 |
| 3 | What the AI sees | The last note plus its position in the piece | Decided 2026-11-09 |
| 4 | How a note is chosen | Three agents in the baseline's order: rhythm, then pitch, then loudness | Decided 2026-11-09 |
| 5 | How it learns | Practice (soft Q-learning), checked against an exact calculation | Decided 2026-11-17 |
| 6 | How strong the rules are / how tight the leash is | Rules matched to real songs; extra settings show the trade-off | Decided 2026-11-17 |
| 7 | What is compared | Section 5 | Decided 2026-11-17 |

## 3. Reward rules: what the training songs say

### 3.1 Three tests

A rule is kept only if it passes all three:

1. **Music research supports it.**
2. **Real songs follow it and the baseline does not.**
   - If real songs don't follow it, the rule pushes the music away from real music.
   - If the baseline already follows it, the rule adds risk and nothing else.
3. **The agent can see what the rule needs.** Points can only depend on the agent's choice and what it sees: its last value and its position in the piece.

All checks use the 80 training songs only. "Baseline" means 1,000 pieces from the n = 1 baseline.

### 3.2 Results

| Rule | Agent | Real training songs | Baseline | Verdict |
|---|---|---|---|---|
| End on the home note (C) | pitch | 84% of songs end on C (67 of 80), although only 21% of all notes are C | 22% of pieces end on C | **Keep** |
| End on a long note (half note or longer) | rhythm | 79% of songs (63 of 80), although only 4% of all notes are that long | 7% of pieces | **Keep** (new candidate) |
| Louder on strong beats | loudness | Beats 1 and 3 are 3.2 velocity steps louder than offbeats; true in 70 of 80 songs | No difference (−0.1) | **Keep**; the effect is small |
| Stay in a comfortable range | pitch | 86% of excerpts stay within an octave of their first note | 24% | **Needs one more fact in the state** (3.5) |
| Pause at phrase ends | rhythm | See 3.6 | See 3.6 | **Drop**: the gap was mostly measurement; the rest is caused by our bar rule |
| Small steps, repeated notes, leaps, staying in key, notes on beat 1 | pitch, rhythm | 68% / 24% / 3.7% / 99.6% / 13.7% | 67% / 24% / 4.0% / 99.6% / 16.1% | **Not needed**: already matched |
| Repeat short patterns | pitch | – | – | **Not possible**: needs memory of more than the last note |

### 3.3 A proper ending: end on C, end on a long note

**Research.**
- In a key, the home note (C here) is the most stable note, so ending on it sounds finished (Krumhansl 1990; Huron 2006).
- A long note marks the end of a phrase (Lerdahl & Jackendoff 1983, grouping rules; Narmour 1990, closure).

**Real songs.** The longer the pause after a note, the more often that note is C:

| Note | Share that is C |
|---|---|
| All notes | 21% |
| Before a rest of at least 1 beat | 30% |
| Before a rest of at least 2 beats | 46% |
| Before a rest of at least 1 bar | 68% |
| Last note of the song | 84% |

- **Last notes of songs:** C 67, A 7, G 3, E 2, D 1.
- **Per song:** C is more common before rests than overall in 43 of the 63 songs that have at least 5 rests.
- **Length:** last notes of songs are long, with a median of 12 sixteenths (a dotted half note), and 79% are a half note or longer. The median of all notes is 2 sixteenths.

**Baseline.**
- 22% of its pieces end on C, the same as C's share of all notes.
- 7% end on a half note or longer.
- It does not know where the piece ends, so it ends anywhere.

**Can the agents see it?**
- The rhythm agent knows the time, so it knows when a note will end the piece.
- The rhythm is made first, so the pitch agent knows how many notes are left, and therefore which note is the last.
- Both rules act on the last note, so together they give the classic ending: a long final C.

**Caveats.**
- The targets come from 80 song endings, so they are uncertain (84% is roughly ±8%).
- Real 8-bar excerpts end on C only 32% of the time, because they are cut at arbitrary bar lines and their last note is usually not a phrase end. Our pieces are complete pieces, so their target comes from the ends of songs.

### 3.4 Louder on strong beats

**Research.** Listeners hear metre as strong and weak beats (Lerdahl & Jackendoff 1983), and performers play strong beats louder (Drake & Palmer 1993).

**Real songs.** Loudness follows the strength of the beat, in order:

| Position | Velocity above the song's median |
|---|---|
| Beat 1 | +1.7 |
| Beat 3 | +1.3 |
| Beats 2 and 4 | +0.8 |
| Eighth offbeats | −0.7 |
| Sixteenth offbeats | −2.7 |

- Beats 1 and 3 are 3.2 velocity steps louder than offbeats, averaged per song, and louder in 70 of the 80 songs.
- The pattern holds among notes of the same length: +1.8 for eighth notes, +1.0 for quarter notes. So it is not only that longer notes are louder.

**Baseline.** No pattern, because the loudness chain does not know the beat.

**Can the agent see it?** Yes. The rhythm is made first, so the loudness agent knows where each note starts.

**Caveat.** The effect is small: about a third of the usual spread of loudness within a song. It may be hard to hear, which is one reason the stronger settings are also run.

### 3.5 Range: the agent cannot see what it needs

Range is the baseline's largest gap: 22.8 semitones per excerpt, against 13.2 in real excerpts.

**Research.** Melodies keep to their own register and drift back toward its middle (von Hippel & Huron 2000).

**A fixed band does not work.**
- Real excerpts sit at very different heights: their middle pitch runs from 60 to 81 (5th to 95th percentile).
- The best-placed band 13 semitones wide holds only 16% of real excerpts, and a band 21 semitones wide holds only 54%.
- A band rule would push the music away from real music, and it would put every piece at the same height.

**Real melodies stay near where they started.**
- On average, the farthest note is 10 semitones from the first note in real excerpts and 17 in the baseline.
- 86% of real excerpts stay within an octave of their first note; only 24% of baseline pieces do.

**The agent sees only the last note.**
- Against a single fixed middle, the baseline already pulls back as strongly as real songs (slope −0.103 against −0.104).
- The missing pull is toward each melody's own middle (real −0.28, baseline −0.15), and an agent that sees only the last note cannot know where that middle is.
- A range rule therefore needs the piece's first note in the state. That is choice 2b in section 8.

### 3.6 Pauses: the gap was mostly how we measured

The baseline report found 22 silent sixteenths per real excerpt and 6 per generated piece. The real excerpts' silence comes from four places:

| Source | Sixteenths |
|---|---|
| Before the first note | 8.5 |
| After the last note | 4.6 |
| Rests between notes | 8.3 |
| Long notes shortened to a kept length | 0.8 |

- **Cutting causes most of it.** 13 of the 22 sixteenths come from cutting excerpts at bar lines, not from the melody. Generated pieces always start with a note at time 0, so they never have this silence.
- **Like with like.** Counting only rests between notes, real excerpts have 8.3 sixteenths and generated pieces 5.9.
- **Our bar rule causes the rest of the gap.**
  - 33% of real rests cross a bar line, and those rests hold 76% of all rest time.
  - If rests may cross bar lines, generated silence rises to 10.6; with no bar rule at all, it is 10.2.
  - A pause reward would therefore only undo our own rule.
- **Phrase pauses have little support anyway.**
  - Real rests most often start late in the bar, on beat 4.
  - Within a song, rests repeat weakly every 2 bars: 68% fall at the busiest phase, against 61% if rests fell at random.
  - They barely repeat every 4 bars (42% against 39%) and not every 8 (28% against 27%).
- **The bar rule has a second cost.** 97% of generated bars have a note on beat 1, against 73% of real bars.

The proposal for the bar rule is in section 8, item 4.

## 4. The MDP

### 4.1 Three agents

The agents run in the baseline's order (Decision 4): rhythm first, then pitch, then loudness.

| Agent | Sees (state) | Chooses (action) | Rule points | Size |
|---|---|---|---|---|
| Rhythm | last length or rest; time used so far (0–127 sixteenths) | the next length or rest that fits in the bar | the piece ends on a note of at least 8 sixteenths | 27 × 128 |
| Pitch | last pitch; notes left | the next pitch | the last note is a C | 37 × up to 128 |
| Loudness | last level; when this note starts | this note's level | louder on beats 1 and 3, softer off the beat | 26 × 128 |

- **Leash points.** At every step, each agent also earns leash points (4.2), based on the baseline's probabilities from the training songs.
- **Episode.** One 8-bar piece.
- **Same states as the baseline (Decision 3).**
  - "Last value" is exactly the baseline chain's state.
  - The clock (time used, or notes left) is what the baseline's own exact sampler already tracks in order to fill 8 bars exactly.
  - So the rhythm and pitch agents see exactly what the baseline generator sees.
  - The loudness agent also sees where its note falls in the bar.
- **Transitions.**
  - For rhythm and pitch, the next state follows directly from the choice.
  - For loudness, the rhythm decides where the next note starts. That is part of the world, not the agent's choice.

### 4.2 The leash (KL-control)

**Score of a piece.** Rule points minus how far the agent's choices moved away from the baseline's probabilities, measured as Kullback–Leibler divergence. This follows Jaques et al. (2017); the mathematics is that of Todorov (2009) and Fox et al. (2016).

**Best behaviour.** It has a simple form: each choice gets the baseline's probability, tilted toward choices that lead to more points:

  π(choice | state) ∝ p_baseline(choice | state) · exp(Q(state, choice))

**Built-in test.**
- With no rule points, the best behaviour is exactly the baseline, including the exact bar filling.
- The baseline's "duration left" sampler is this same calculation with the bar rule as the only rule.
- So with all rule strengths at zero, the MDP must reproduce the baseline's probabilities exactly.

### 4.3 Rule strength (Decision 6)

**Proposal.**
- The leash weight is 1.
- Each rule's strength is the value at which generated pieces follow the rule as often as real training songs do:
  - 84% of pieces end on C;
  - 79% end on a half note or longer;
  - beats 1 and 3 are 3.2 velocity steps louder than offbeats.
- Each strength is found by a simple search, using the exact calculation.
- Each agent has one rule, so the three searches are independent.

**Why.**
- Among all ways of following a rule this often, this one stays closest to the baseline. This is the maximum-entropy principle (Jaynes 1957), the same idea Khalifa et al. (2021) use for controlling text generators.
- It needs no taste-based choice, and it uses training songs only.

**Trade-off curve.**
- The other strengths run are 0, 0.5, 2 and 4 times the matched ones.
- At 0 times, the result must equal the baseline.

**Alternative (Jaques style).**
- Give each rule a fixed number of points, such as +1, and vary the leash instead.
- The main setting would then have to be picked on the validation songs, by a rule fixed in advance.

### 4.4 Learning (Decision 5)

- **Practice: soft Q-learning** (G-learning; Fox et al. 2016). The agent makes pieces with its current behaviour, sees the points, and updates its table.
- **Answer key: exact calculation.** The tables are small, so the best behaviour can be computed backward from the end of the piece. This is the same recursion as the baseline's sampler.
  - For the loudness agent, the answer key uses how often each next position follows in the rhythm agent's pieces.
- **Stopping.** Practice stops when it is within 0.01 bits of the answer key, averaged over the states the pieces visit, or when it reaches a fixed budget. The learning curve is reported.
- **Evaluation pieces** come from the practised behaviour, with the exact one reported alongside.

### 4.5 Comparison: data as starting point only (Decision 1)

- The table starts so that the first behaviour equals the baseline.
- Learning uses rule points only, with no leash.
- Choices are limited to those the training songs contain after the current state.
- Choices are sampled in the same way, with the same practice budget, and the statistics are recorded during practice.
- Expected result: it forgets the data's preferences. For example, pitch steps would no longer be mostly small.

## 5. Conditions compared

Every condition runs under the baseline's conditions:
- the same songs;
- 8-bar pieces with the same bar rule;
- 200 attempts per condition;
- fixed seeds.

| Condition | Why |
|---|---|
| Real test excerpts, real training excerpts | The target, and how much real music varies |
| Baseline (n = 1) | What we compare against |
| **MDP: three rules, matched strength, leash** | The main result |
| MDP at 0.5×, 2× and 4× strength | The trade-off curve |
| MDP at 0× | Must equal the baseline (a check) |
| MDP, data as starting point only | What the leash prevents |
| MDP with one rule removed, three times | Which rule causes which effect |
| Optional: range variant (2b) | Can RL narrow the range without the copying that longer memory brings? |
| Optional: baseline with rhythm memory 2 | The open rhythm question; marked as added after seeing results |

## 6. Measures

1. **The rules themselves.** Share of pieces ending on C, share ending on a long note, and the strong-beat loudness difference, for real songs, the baseline and each MDP.
2. **Everything from the baseline report:**
   - distances from the test songs (total variation) and entropy;
   - per-piece features with KS distance, with the corrected silence measure;
   - copying per view (melody, pitch steps, lengths, loudness);
   - variety.
3. **Policy change:**
   - how far the policy moved from the baseline's probabilities (average KL over the states the pieces visit);
   - which choices gained or lost the most;
   - where in the piece the changes happen. This shows the planning: the notes before the end change too, to prepare the ending.
4. **Listening test.** To be planned separately.

Prediction bits on test songs are not reported for the MDP. Its choices depend on where the piece ends, which a whole test song does not have.

## 7. Fixed in advance

- Rule targets come from training songs only, and are the numbers above.
- Strength multipliers are 0, 0.5, 1, 2 and 4.
- The stopping rule for practice and the seeds are fixed, with 200 attempts per condition.
- The rules kept and dropped are decided now. A rule added after seeing MDP results will be labelled as such.
- The test songs are used once, after everything else is fixed.

## 8. Decided 2026-11-17 (all as recommended below)

1. **2a. Which rules?** Recommended: the three that pass (end on C, end on a long note, louder on strong beats). You could drop the loudness rule as too subtle, but then the loudness agent has nothing to learn.
2. **2b. Range?** The options:
   - (i) Leave it out and report it as a limit of one-note memory.
   - (ii) Add an extra variant whose pitch agent also knows the piece's first note, with the rule "stay within an octave of it". Real target: 98.6% of notes.

   Recommended: (ii), as an extra after the main version works, not as the main result. It addresses the baseline's largest gap. It also lets us compare it with the longer-memory chains, which narrow the range only by copying.
3. **2c. How strong are the rules?** Recommended: matched to real songs (4.3), rather than fixed points with a leash sweep.
4. **The bar rule and silence.** Recommended:
   - keep the bar rule unchanged for every condition, so the MDP runs under the baseline's conditions;
   - correct the silence measure to count only rests between notes, for real and generated pieces alike;
   - report the bar rule's cost (less silence, too many notes on beat 1) as a limit.
5. **Confirm decisions 5–7** as proposed.

## 9. Risks and limits

- **Small effects.** The loudness accent may not be audible at the real size.
- **Few endings.** The ending targets rest on 80 songs.
- **Separate agents.** Nothing links pitch with length or loudness, as in the baseline. The long final C comes from two separate rules that act on the same note.
- **Range.** The main MDP cannot fix the range; only the range variant can.
- **Bar rule.** It stays, so silence and beat-1 notes remain off.
- **Listening.** The listening test is not designed yet.

## 10. Build steps, after your go-ahead

1. Write the exact calculation for the three agents. Add a test that zero rule strength gives exactly the baseline's probabilities.
2. Add the rules and find the strengths that match real songs.
3. Add soft Q-learning practice and check that it agrees with the exact calculation.
4. Add the "starting point only" version.
5. Run all conditions, and write `results/mdp/` and `reports/mdp_report.md`.
6. Optional: the range variant.
7. Plan the listening test.

## References

- Drake, C. & Palmer, C. (1993). Accent structures in music performance. *Music Perception* 10(3).
- Fox, R., Pakman, A. & Tishby, N. (2016). Taming the noise in reinforcement learning via soft updates. *UAI*.
- Huron, D. (2006). *Sweet Anticipation: Music and the Psychology of Expectation*. MIT Press.
- Jaques, N. et al. (2017). Sequence Tutor: conservative fine-tuning of sequence generation models with KL-control. *ICML*.
- Jaynes, E. T. (1957). Information theory and statistical mechanics. *Physical Review* 106(4).
- Khalifa, M., Elsahar, H. & Dymetman, M. (2021). A distributional approach to controlled text generation. *ICLR*.
- Krumhansl, C. L. (1990). *Cognitive Foundations of Musical Pitch*. Oxford University Press.
- Lerdahl, F. & Jackendoff, R. (1983). *A Generative Theory of Tonal Music*. MIT Press.
- Narmour, E. (1990). *The Analysis and Cognition of Basic Melodic Structures*. University of Chicago Press.
- Schulze, W. & van der Merwe, B. (2011). Music generation with Markov models. *IEEE MultiMedia* 18(3).
- Todorov, E. (2009). Efficient computation of optimal actions. *PNAS* 106(28).
- von Hippel, P. & Huron, D. (2000). Why do skips precede reversals? The effect of tessitura on melodic structure. *Music Perception* 18(1).
