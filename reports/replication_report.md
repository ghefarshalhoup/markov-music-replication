# Replication report: "Music Generation with Markov Models" (Schulze & van der Merwe, 2011)

Phase 1 of Extension 10. All numbers come from `results/summary.md`
(200 generation attempts per setting, fixed seeds) and `tests/test_paper_examples.py`.

## Summary

We rebuilt the paper's system (SuperWillow) from its description and trained it on
**the paper's own training pieces**, which the authors published on the project
website. The worked examples printed in the paper are reproduced exactly. The paper's
claims about how far each model's memory can go are mostly reproduced, with one
important addition: **at long memory lengths, the only pieces the higher-order model
can produce are note-for-note copies of a training piece.** The paper's listening
survey cannot be replicated without human listeners; the pieces for it are ready.

| # | What the paper reports | What we found | Replicated? |
|---|---|---|---|
| 1 | HMM example (Table 1, Figure 2): transition matrix *a*, start probabilities *π*, confusion matrix *b* | Identical fractions | **Yes, exact** |
| 2 | Prediction suffix automaton example (Figure 1) | Identical 13 states and transitions, including the details "de is added only as a parent" and "dc, ec are added only to make dcd, ecd reachable" | **Yes, exact** (needs "a context seen once can count") |
| 3 | Melodic-arc encoding example (Figure 4): hidden {=4, +2, +4, −1, +3, −1}, observed {IV, IV, IV, V, V, VI} | Observed identical; hidden identical except the 5th symbol, where we get +5 | **Yes, with a typo found in the paper**: g is the 5th degree, so "+3" contradicts the paper's own definition |
| 4 | Melted style: higher order only works up to memory length 2 ("sparseness") | At 8 bars: L=1 100 %, L=2 54 %, L=3 8 %, L=4–6 at most 0.5 % of attempts succeed. From L=7 successes return, but every one is a verbatim copy of a training piece | **Yes**, if verbatim copies are not counted as generating |
| 5 | Melted style: mixed order works up to memory length 5 | Depends on a threshold the paper doesn't give. With the setting that reproduces Figure 1, mixed order behaves like higher order (limit 2–3). With "a context must be seen at least twice", it works up to 10 | **Partly**: the direction matches; the exact limit can't be pinned down |
| 6 | Burger style: both models work up to memory length 10 | Mixed (seen-twice setting): 100 % at every L, no copying. Higher order: new pieces only up to L=5; from L=6 only verbatim copies (at most 1 % of attempts at 8 bars, 11 % at 9 bars) | **Mixed yes; higher order only by copying** |
| 7 | Mixed order reaches much longer memory than higher order | Mixed (seen-twice) still succeeds at L=10 and uses up to 9 previous notes, while staying original; higher order at that length can only copy | **Yes** |
| 8 | The steps don't coordinate, so compositions fail, e.g. the rhythm can't fit the chord durations | Failures happen, and always because one step can't satisfy what an earlier step produced. But they occur in the chord-progression and melody steps; the rhythm step never failed | **Partly**: same cause, different failing step |
| 9 | Generated music may copy training too closely; "a thorough investigation … is still required" | Measured (section 3.4): low memory → 11–29 % of a melody is the longest copied stretch; high memory → verbatim copies. The paper's own published pieces copy 8–21 %, which fits low memory lengths | **New result** (the paper left this open) |
| 10 | Survey: 38 % mistook a computer piece for human; 59 % preferred a computer piece | Needs human listeners. Stimuli are in `results/examples/` | **Not yet** |
| 11 | Smoothing does not improve quality | Needs listening; not tested | **No** |

## 1. Data

The paper's training pieces were found on the SuperWillow project website, in the
same two styles as the survey:

| Style | Pieces | Bars | Melody notes |
|---|---|---|---|
| Burger | 4 by Eduard Burger | 9, 10, 13, 8 | 216 |
| Melted | 2 by J. C. Dalton, 1 by affron5, 1 by MindAtrophy | 9, 8, 8, 17 | 223 |

Every piece has a monophonic "Lead" part and a block-chord "Accompaniment" part,
is in 4/4 and C major, and has no rests or tied notes, exactly matching the
paper's composition rules. **Every note is marked forte**, so the paper's data
holds no loudness (velocity) information at all.

We also downloaded the paper's own generated pieces from the same website: per
style two mixed-order and one higher-order piece (b2, b4, b5; m2, m4, m5). Three
computer pieces per style is the number the paper says it chose for the survey,
so these are very likely the survey pieces.

## 2. What we built, and choices the paper leaves open

| Paper component | Our implementation |
|---|---|
| Extraction: transpose to C, classify chords | `analysis.py`, `theory.py` |
| Chord-duration MC (repeated chords merged) | `analysis.merge_chords` + `models.py` |
| Chord-progression MC over Roman numerals | `models.py` |
| Rhythm MC over note values | `models.py` |
| Melodic-arc HMM: hidden = contour + scale degree, observed = chord numeral | `hmm.py` |
| Higher-order MC (L-th order) | `models.HigherOrderMC` |
| Mixed order: prediction suffix automaton learned with LearnPSA | `models.PSA` |
| Start and final states | START/END symbols in every model |
| "Duration left" construction so pieces end exactly at the requested length | `generate.sample_constrained` |
| Sampling with Carmel; melody by noisy-channel decoding | exact conditional sampling (dynamic programming), melody by forward filtering–backward sampling |

Where the paper doesn't say how something was done, we chose as follows:

- **Chord recognition.** A chord's root and type come from its set of notes, so
  inversions are recognised (E4+A4+C5 is A minor). When two readings fit equally,
  the bass note decides. All 110 training chords are recognised.
- **Roman numerals** give only the root's position in the scale, ignoring
  major/minor, as the paper states ("the place of each root key in the scale").
- **Chord voicing at generation:** the chord's notes placed in one octave, as in
  the paper's published pieces.
- **Rhythm** is learned from the lead. The paper says the rhythm analysis "is
  applied to the accompaniment and lead voice", which is ambiguous.
- **Melody notes must fit inside a chord and a bar.** This follows the paper's
  composition rules and its remark that rhythm must "fit into the generated chord
  durations".
- **Melody start octave:** taken from the first notes of the training pieces.
  The other notes follow from the contour (move to the nearest note with that
  degree, up or down). The paper's published pieces decode perfectly with this
  rule (100 % of notes in all six), which suggests it matches the original.
- **PSA thresholds** are not given in the paper. We ran two settings:
  "seen once" (reproduces Figure 1 exactly) and "seen at least twice".
- **No smoothing**, following the paper's remark that smoothing didn't help.
- **Length:** 8 bars as the main setting (the paper's "more or less eight
  measures"); 7–10 bars as a sensitivity check, since the paper's own pieces are
  7–10 bars long.

## 3. Results

### 3.1 Worked examples (tests)

`tests/test_paper_examples.py` checks Table 1/Figure 2, Figure 1 and Figure 4
directly; all 8 tests pass. Figure 1 is reproduced only when a context seen once
may be kept, because the context "ede" occurs once in the example. Any growth
ratio up to 1.2 then gives the exact figure.

### 3.2 How far can memory go? (claims 4–7)

Share of 200 attempts that produced a complete 8-bar piece. L is the memory
length; "mixed ≥2" is the PSA with the seen-twice threshold.

| L | Burger higher | Burger mixed | Burger mixed ≥2 | Melted higher | Melted mixed | Melted mixed ≥2 |
|---|---|---|---|---|---|---|
| 1 | 100 % | 100 % | 100 % | 100 % | 100 % | 98 % |
| 2 | 100 % | 100 % | 100 % | 54 % | 54 % | 91 % |
| 3 | 100 % | 100 % | 100 % | 8 % | 6 % | 90 % |
| 4 | 63 % | 62 % | 100 % | 0.5 % | 0 % | 93 % |
| 5 | 42 % | 38 % | 100 % | 0 % | 0 % | 88 % |
| 6 | 0.5 %\* | 1 %\* | 100 % | 0 % | 0 % | 90 % |
| 7 | 1 %\* | 1.5 %\* | 100 % | 18 %\* | 12 %\* | 88 % |
| 8 | 1 %\* | 0 % | 100 % | 31 %\* | 37 %\* | 87 % |
| 9 | 1 %\* | 0.5 %\* | 100 % | 56 %\* | 44 %\* | 91 % |
| 10 | 0 % | 0.5 %\* | 100 % | 50 %\* | 50 %\* | 90 % |

\* every successful piece is a verbatim copy of a training piece.

The pattern explains the paper's "sparseness" remark. With memory 4–6, each model
mixes fragments of different training pieces. The four models no longer fit
together, so almost every attempt fails. With memory 7–10, each model can only
replay one training piece from start to finish. That succeeds when a training
piece has exactly the requested length (Melted has two 8-bar pieces; Burger has
one), and the result is a copy. Allowing 7–10 bars moves the numbers but not the
pattern (`results/summary.md`).

For Melted at 8 bars, the higher-order limit matches the paper's "up to two":
reliable at 1, about half the attempts at 2, rare at 3, impossible at 4–6. For
Burger, the paper's "higher order up to 10" is only reachable by copying.

How much memory the melody model actually used (mean / maximum previous notes),
Burger:

| L | higher | mixed ≥2 |
|---|---|---|
| 3 | 2.9 / 3 | 2.2 / 3 |
| 5 | 4.7 / 5 | 2.6 / 5 |
| 9 | 8.0 / 9 (copies only) | 2.8 / 9 |

The mixed model uses long memory only where it changes the prediction. That is
why it can be given memory 10 and still produce new pieces: the paper's claim 7.

### 3.3 Failed compositions (claim 8)

Rhythm and chord durations never failed. Failures came from:

- **Chord progression:** the chord-duration step chose a number of chords for
  which no progression of exactly that length ends properly.
- **Melody:** no melody fits the chord under every note. This is by far the
  most common failure (for example 93 of 200 Melted attempts at L=2).

Both are cases of "steps that do not take each other into account", as the paper
says. Our rhythm step never fails because it is sampled exactly under the chord
boundaries. The original system's rhythm failures probably came from a less exact
constraint, but the paper gives no details.

### 3.4 Copying from training (claim 9, the paper's open question)

For each 8-bar piece: the longest stretch of melody (intervals and durations)
that also appears in a training piece, as a share of the whole melody.
Burger / Melted:

| L | higher | mixed ≥2 |
|---|---|---|
| 1 | 11 % / 12 % | 11 % / 13 % |
| 2 | 15 % / 11 % | 14 % / 14 % |
| 3 | 19 % / 13 % | 13 % / 13 % |
| 4 | 29 % / 23 % | 14 % / 14 % |
| 5 | 25 % / – | 13 % / 13 % |
| 7–10 | 100 % (verbatim) | 14–21 % |

The paper's published pieces score b2 8 %, b4 21 %, b5 11 % (Burger) and m2 10 %,
m4 9 %, m5 9 % (Melted). That is the range of our models at memory 1–3, so the
survey pieces were most likely generated with short memory, not with the maximum
lengths the paper mentions. Our pieces and the paper's pieces also share visible
material, because both draw on the same training phrases. For example, the
paper's m2 starts with the opening of Dalton's first piece.

### 3.5 Our pieces next to the paper's pieces

Distance to the training data (total variation: 0 = same distribution, 1 =
nothing in common) for note durations and chord numerals, plus simple
descriptors. Burger:

| set | notes per bar | ends on C | durations | numerals |
|---|---|---|---|---|
| training | 5.5 | 100 % | 0 | 0 |
| paper's pieces | 7.7 | 100 % | 0.21 | 0.15 |
| ours higher L=2 | 5.2 | 100 % | 0.05 | 0.06 |
| ours mixed L=2 | 5.1 | 100 % | 0.03 | 0.07 |

Melted:

| set | notes per bar | ends on C | durations | numerals |
|---|---|---|---|---|
| training | 5.1 | 50 % | 0 | 0 |
| paper's pieces | 5.9 | 67 % | 0.06 | 0.22 |
| ours higher L=2 | 5.3 | 59 % | 0.02 | 0.04 |
| ours mixed L=2 | 5.4 | 56 % | 0.04 | 0.03 |

Our pieces are statistically at least as close to the training style as the
paper's pieces. The paper's Burger pieces are busier, with more sixteenth notes,
than their training data. With three pieces per style this is a rough comparison,
and it says nothing about how the pieces sound.

### 3.6 A limit of the paper's melody representation

The hidden melody symbol stores direction and scale degree but not the octave, so
a leap larger than an octave cannot be represented. This is rare (1 of 212
intervals in Burger, 1 of 219 in Melted), but when it happens the rest of the
melody comes out an octave off. The paper doesn't mention this.

## 4. Not replicated

- **The listening survey** (38 % mistook a computer piece for human; 59 %
  preferred at least one computer piece). It needs human participants.
  `results/examples/` has, per style, the human training pieces and generated
  pieces at several memory lengths, all as MusicXML and MIDI through the same
  renderer, so a small version of the survey can be run.
- **The smoothing remark**, which is about musical quality and also needs
  listeners.
- **Loudness/velocity:** the paper's data has none (every note forte), so there
  is nothing to replicate. Velocity has to be learned from Aria-MIDI in Phase 1B.

## 5. What this means for the next steps

- With about 220 melody notes per style, anything beyond a memory of about 5
  turns into copying. Phase 2's reinforcement learning on this data would mostly
  learn to reproduce training pieces, so it needs the much larger Aria-MIDI corpus
  (Phase 1B) to be meaningful.
- The copying measure (3.4) and the step-failure counts (3.3) are useful
  baselines to report for the Phase 2 model as well.

## 6. Reproduce

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe scripts/run_replication.py --attempts 200
```
