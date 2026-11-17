# POP909 baseline report

Phase 1B of Extension 10: an n-th order Markov chain generator for pitch, length and loudness, trained on POP909. All numbers come from `results/baseline/summary.md` (200 generation attempts per setting, fixed seeds). The choices behind it are in `reports/pop909_audit_rules.md`.

## Summary

The baseline works, and its strengths and weaknesses are clear:

- **Memory length:** the validation songs chose **n = 1 for all three chains**. Each chain looks only at its own last value.
- **Pitch:** memory clearly helps, on all 10 test songs.
- **Loudness:** memory helps moderately, on 9 of 10 test songs.
- **Rhythm:** memory helps only a little, and 10 test songs cannot show that the gain is real.
- **Overall statistics** of the pieces fall within the range of real songs.
- **Individual pieces** differ from real excerpts in two clear ways: their pitch range is too wide, and they have too little silence.
- **Copying:** pieces copy no more than real test excerpts do. Copying rises strongly with longer memory, as the paper warns.

Nobody has listened to the pieces yet, so this report says nothing about how they sound.

| Check (from the plan) | Result | Passed? |
|---|---|---|
| Code is correct | 38 tests pass; the data step gives the audit's numbers again (335 songs, 114,187 notes, eighth note 48.8%, 3.4 rests per 100 notes) | **Yes** |
| Each chain predicts test songs better than no memory, which beats random | True for all three, but the rhythm gain could be zero (95% interval −0.182 to +0.025 bits) | **Yes for pitch and loudness; unclear for rhythm** |
| Statistics are closer to the test songs than no memory, compared with how much real songs differ | Pitch steps and loudness steps are much closer; length pairs tie (0.219 vs 0.218). All 7 statistics are within the real-song range | **Yes for pitch and loudness; no for rhythm** |
| It doesn't just copy | 0% full copies; longest copied run 9% of the melody, against 12% for real test excerpts | **Yes** |
| Paper's claim: copying rises and variety falls as n grows | Copying rises in each chain. The variety measures barely move | **Copying yes; variety no** |

Two details go beyond the plan:
- the plan asked only whether each chain beats no memory; we also report a 95% interval over test songs, which is stricter;
- real excerpts need at least 8 notes, so that instrumental breaks are not compared with melody.

## 1. What was built

1. **Songs.** 100 songs drawn at random with the fixed seed from the 335 major-key, single-key songs: 80 training, 10 validation, 10 test. They hold 28,268, 3,219 and 3,744 melody notes.
2. **Symbols, learned from the training songs only.**
   - 27 note and rest lengths, covering 99% of the training notes and rests.
   - 37 pitches, as actual notes after moving to C.
   - 26 loudness levels, relative to each song's median.
3. **Chains.** Three separate chains, each counting what follows its own last n values, for n from 1 to 8. A no-memory chain (n = 0) is the reference.
4. **Generation.** Rhythm comes first and fills exactly 8 bars, with no note or rest crossing a bar line. Then come as many pitches and loudness levels as the rhythm has notes.

The code reuses the replication's chain and exact-fit sampler. Moving the shared code changed nothing: the audit's output files are byte-identical, and a full re-run of the replication gives identical results.

## 2. Memory length: n = 1

Bits per symbol on the validation songs (lower is better). These chose n; the test songs were not used.

| n | length | pitch | loudness |
|---|---|---|---|
| 0 (no memory) | 2.499 | 4.136 | 4.404 |
| **1** | **2.328** | **2.785** | **4.185** |
| 2 | 2.353 | 2.884 | 4.634 |
| 3 | 2.449 | 3.253 | 5.334 |
| 4 | 2.618 | 3.747 | 5.651 |
| 8 | 3.554 | 4.547 | 5.753 |

Beyond n = 1, predictions of new songs get worse under Witten–Bell smoothing. This answer is not equally firm for all three chains. We tested it on the validation songs only, in two ways: redrawing those songs, and trusting the shorter memory by a fixed weight w instead of Witten–Bell.

| Chain | n = 1 wins when the songs are redrawn | Best n with other smoothing |
|---|---|---|
| Loudness | 100% | always 1 |
| Pitch | 92% | 1, or 2 with strong smoothing (w ≥ 30), gaining only 0.02 bits |
| Length | 68% | 1, or 2–3 with stronger smoothing (w ≥ 10), reaching 2.199 bits at w = 100 against 2.328 |

So loudness memory is firmly short, and pitch memory is short or nearly so. **Rhythm probably has more to gain from longer memory than n = 1 shows.** Witten–Bell seems to trust rarely seen contexts too much. A likely reason is that songs repeat their own sections, which makes a context look more reliable than it is in a new song; we did not test this.

We keep n = 1, because that was the rule fixed in advance, and we changed nothing after seeing these results.

## 3. Predicting the test songs

| Chain | Symbols | Random guess | No memory | n = 1 | Gain (95% interval over songs) | Test songs improved |
|---|---|---|---|---|---|---|
| Length | 27 | 4.807 | 2.476 | 2.389 | −0.088 (−0.182 to +0.025) | 7 of 10 |
| Pitch | 37 | 5.248 | 4.078 | 2.906 | −1.173 (−1.526 to −0.863) | 10 of 10 |
| Loudness | 26 | 4.755 | 4.504 | 4.251 | −0.253 (−0.361 to −0.136) | 9 of 10 |

All three together, per note: random 14.96 bits, no memory 11.14, n = 1 9.62.

The previous note says a lot about the next pitch, because melodies mostly move by small steps. It says much less about the next length. One possible reason, not tested, is that the rhythm chain doesn't know where in the bar it is.

## 4. Resemblance to real music

**Across all pieces together.** Total variation distance from the test songs (0 = identical). "Real songs" means random groups of 10 training songs.

| Statistic | Real songs: mean (5th to 95th percentile) | Baseline | No memory |
|---|---|---|---|
| Pitch | 0.176 (0.112 to 0.263) | 0.109 | 0.107 |
| Pitch class | 0.076 (0.043 to 0.108) | 0.060 | 0.059 |
| **Pitch step** | 0.102 (0.065 to 0.152) | **0.074** | 0.510 |
| Length | 0.133 (0.060 to 0.247) | 0.130 | 0.091 |
| Length pair | 0.247 (0.172 to 0.369) | 0.219 | 0.218 |
| Loudness | 0.205 (0.154 to 0.253) | 0.162 | 0.152 |
| **Loudness step** | 0.129 (0.098 to 0.162) | **0.090** | 0.196 |

A no-memory model matches plain frequencies by construction, so only the step and pair rows can show what memory adds. Memory clearly helps for pitch and loudness, and not for rhythm. The rhythm chain is also slightly worse than no memory on single lengths (0.130 vs 0.091). Real rhythms vary more than generated ones: length entropy is 2.43 bits on the test songs against 2.10 for the baseline.

**Piece by piece.** Means over 8-bar pieces, with the distance from real test excerpts in brackets (Kolmogorov–Smirnov: 0 = same, 1 = no overlap). Training excerpts show how far real music differs from itself.

| Feature | Test excerpts | Training excerpts | Baseline | No memory |
|---|---|---|---|---|
| **Pitch range (semitones)** | 13.5 | 13.2 (0.11) | **22.6 (0.83)** | 29.7 (1.00) |
| **Distinct pitches** | 8.5 | 7.4 (0.33) | **12.0 (0.76)** | 15.1 (0.97) |
| **Notes** | 40.1 | 37.4 (0.13) | **48.3 (0.44)** | 48.2 (0.45) |
| **Silent sixteenths (of 128)** | 20.8 | 22.2 (0.16) | **5.8 (0.33)** | 8.3 (0.30) |
| Mean step size | 2.4 | 2.4 (0.17) | 2.4 (0.09) | 8.1 (1.00) |
| Rests | 1.3 | 1.1 (0.15) | 0.9 (0.17) | 1.3 (0.27) |
| Loudness range (levels) | 20.2 | 17.5 (0.27) | 23.6 (0.48) | 24.3 (0.58) |
| Mean loudness step (levels) | 5.5 | 4.7 (0.19) | 5.0 (0.37) | 7.0 (0.49) |

The main weaknesses are in bold, and both appear in the training excerpts too, so they do not depend on the test songs:

- **Too wide a range.** The steps are the right size (2.4 semitones), but with one note of memory nothing keeps a melody in one register. It wanders almost twice as far as a real one. Longer memory narrows it (n = 7: 14.1 semitones), but only by copying (section 5).
- **Too little silence, so too many notes.** Real excerpts are silent for about 21 sixteenths, generated ones for about 6. Three things probably contribute, and we did not separate them: the bar rule (33% of real rests cross a bar line), merging long rests into shorter ones, and silence before the first note or after the last one in real excerpts.

## 5. Copying and variety: the paper's claims

Longest stretch copied from a training song, as a share of the piece:

| n | Melody (pitch step + length) | Pitch steps | Lengths | Loudness | Full copies: pitch / lengths / loudness |
|---|---|---|---|---|---|
| Real test excerpts | 12% | 21% | 30% | 14% | 0% (melody) |
| 1 (baseline) | 9% | 15% | 26% | 10% | 0 / 0 / 0% |
| 2 | 10% | 16% | 28% | 12% | 0 / 0 / 0% |
| 3 | 11% | 18% | 30% | 23% | 0 / 0 / 0% |
| 4 | 11% | 24% | 31% | 55% | 0 / 0 / 9% |
| 5 | 12% | 36% | 36% | 81% | 0 / 0 / 42% |
| 6 | 11% | 55% | 44% | 92% | 5 / 0 / 73% |
| 7 | 11% | 74% | 54% | 96% | 26 / 15 / 80% |
| 8 | 12% | 83% | 59% | 98% | 32 / 7 / 89% |

- **Copying rises with n: confirmed, chain by chain.** Loudness starts copying first (n = 4), then pitch (n = 6). The melody column stays flat only because the chains are separate: pitch can copy one song while rhythm copies another, so the pair never lines up. Melody copying alone would miss this.
- **Failed attempts: not seen.** Every setting succeeded 100% of the time, while in the paper's small data, higher-order models stopped working around n = 2. Probably the much larger data, the missing chord step and the missing end-of-piece symbol all help. In this data, too little evidence shows up as copying, not as failure.
- **Variety falling: not seen.** All pieces are unique at every n, and the overlap between pairs barely changes. High-n pieces can copy from 80 different songs, and the chains copy independently, so these measures would not show the problem.
- **Real music repeats more.** Pairs of real excerpts share more melody 4-grams (0.019) than generated pairs (0.001), probably because songs repeat their sections. Generated pieces have no such structure. On rhythm alone the reverse holds: generated pairs overlap more (0.158 vs 0.088).

## 6. Limits

- **No listening yet.** The checks above measure statistics, not musical quality. 23 MIDI files are in `results/baseline/examples/` for listening: 18 generated, 5 real. Reading them back confirms that notes and loudness vary and that generated pieces end by bar 8.
- **Generated and real examples are not yet comparable for a listening test.** Every note is held until the next one starts, because note ends are not modelled. Long silences in real excerpts are shortened, so some come out under 8 bars (`real_test_1` ends at bar 3.3). A listening test needs a fairer choice of real excerpts.
- **10 test songs are few.** That was the decision (a small corpus), and it is why the rhythm result is unclear.
- **Scope.** Findings apply to major-key pop melodies, without chords.
- **Chains are independent.** Nothing links a note's pitch to its length or loudness.

## 7. What this means for the MDP

- **State.** With n = 1, the shared state is the last note: at most 27 × 37 × 26 ≈ 26,000 combinations, which a table can handle. Rhythm is the chain most likely to want more memory.
- **What a reward could fix.** The baseline's clearest gaps are pitch range and silence, both measurable on the training songs alone (range 13.2 semitones, 22 silent sixteenths). They are candidates for reward terms, to be justified and tested in the MDP plan.
- **What to watch.** Longer memory narrows the range only by copying. The MDP has to improve the range without that side effect, so its comparison must include copying per chain, not only for the melody.

## Reproduce

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -I scripts/run_baseline.py --attempts 200
```

The run takes about 30 seconds and writes `results/baseline/summary.md`, `results.json`, `songs.json` and `examples/`.
