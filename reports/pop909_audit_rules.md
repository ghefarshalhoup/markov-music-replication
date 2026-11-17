# POP909 data audit: decision rules (fixed before measuring)

Written 2026-10-27, before the full POP909 download and before any audit statistic was computed.

**What we had seen beforehand:**
- an 8-song sample (2026-10-26): velocity ranges, and grid alignment of song 001;
- the POP909 paper and README: file formats.

The thresholds below were proposed after that sample and are fixed here. The audit script applies them as written. Any later change will be reported as a deviation, with the reason.

## Source of each fact

| Fact | Source |
|---|---|
| Notes, velocities, tracks | `POP909/NNN/NNN.mid`, final version only (the `versions/` folders are drafts) |
| Beat times | `beat_midi.txt`, column 1 (seconds) |
| Metre | `index.xlsx`: beats per measure and quavers per measure, one value per song |
| Key | `key_audio.txt`: start, end, key label; one line per key segment |

Only the **MELODY** track is audited, because the baseline models the lead line.

## Shared definitions

- **Position on the grid.** A time *t* falls between labelled beats *b_i* and *b_(i+1)*. Its position in sixteenths is 4·i + 4·(t − b_i)/(b_(i+1) − b_i). Before the first or after the last beat, the first or last beat interval is extrapolated.
- **Distance to the grid.** The distance from that position to the nearest whole sixteenth, converted to milliseconds with the local beat length.
- **Melody clean-up (rule 12)** is applied before rests (rule 11) and velocity (rules 13–15) are measured.
- **Order of filters:**
  1. metre (rule 10)
  2. timing grid (rule 9)
  3. constant velocity (rule 15)
  4. key changes (rule 16)

  Rules 11–14 are measured on the songs that remain. The number of songs left after each filter is reported.

## Rules

### 9. Timing grid
- **Measure:** per song, the share of melody note onsets within 20 ms of a sixteenth position (p16).
- **Also reported, without a rule:** the share of note ends within 20 ms; how many failing songs would pass on a combined sixteenth + triplet grid.
- **Rule:** keep a song if p16 ≥ 0.95. The grid is sixteenths, as in the paper and POP909's own baseline; triplets are not added.

### 10. Metre
- **Measure:** beats per measure and quavers per measure from `index.xlsx`.
- **Rule:** keep songs with 4 beats and 8 quavers per measure (simple 4/4). The paper's data was all 4/4. Compound metres such as 12/8 are excluded.
- **Clarification** (added after reading the file header, before any statistic was computed): the README says "quavers per measure", but the index column is `num_quavers_per_beat`. The rule is unchanged: 4/4 means `num_beats_per_measure` = 4 and `num_quavers_per_beat` = 2 (2 × 4 = 8 quavers per measure).

### 11. Rests
- **Measure** (after clean-up and quantisation to sixteenths):
  - the gap between a note's end and the next onset; a gap of at least one sixteenth counts as a rest;
  - the share of melody notes followed by a rest;
  - the distribution of rest lengths;
  - the share of rests of at least one bar.
- **Rule:** if ≥ 5% of melody notes are followed by a rest, rests become their own symbol (with a duration). Otherwise each gap is added to the note before it (the paper's no-rest style).

### 12. Overlapping and simultaneous notes
- **Measure:**
  - the share of melody notes that end after the next note starts (overlap), and the median overlap;
  - the share of onsets that start within 20 ms of another melody onset (simultaneous).
- **Rule (always applied, measured to show its size):** cut a note at the next onset; when notes start within 20 ms of each other, keep the highest pitch.

### 13. Number of velocity levels
- **Measure:** on the representation chosen by rule 14, the share of information kept: H(Q_k(V)) / H(V), in bits, over all melody notes. Q_k is equal-frequency (quantile) binning into k levels.
- **Rule:** choose the smallest k from 2 to 64 with H(Q_k(V)) / H(V) ≥ 0.90. The RMS quantisation error at that k is also reported.
- **Note:** the bin edges used by the baseline will be recomputed on the training split only. The audit uses all kept songs just to choose k.

### 14. Absolute or relative velocity
- **Measure:** the share of melody-velocity variance that lies between songs:
  η² = Σ_s n_s (mean_s − mean)² / Σ (v − mean)².
- **Rule:** if η² ≥ 0.50, velocity is measured relative to the song: v − median_s (the song's median melody velocity). Otherwise absolute MIDI velocity is used.

### 15. Songs with constant velocity
- **Measure:** per song, the number of distinct melody velocity values and their standard deviation.
- **Rule:** exclude a song only if its melody has a single velocity value, because then velocity carries no information. Songs with low but real dynamics are kept, so the corpus is not biased toward dynamic songs. We report how many songs have a standard deviation below 2.

### 16. Key changes
- **Measure:** the number of key segments per song, and the key and mode labels.
- **Rule:**
  - If at most 10% of songs change key, exclude those songs.
  - If more do, split them at each change; each part keeps its own key, and parts shorter than 8 bars are dropped.
  - Every remaining part is transposed: major to C major, minor to C minor (the paper's rule).

## Deviations

### Deviation 1: rule 10 (metre), 2026-10-27, before any other statistic was computed

**What we found:** applying rule 10 as written would exclude every song. The index never says 4 beats per measure:

| (beats per measure, quavers per beat) | Songs |
|---|---|
| (2, 2) | 857 |
| (3, 2) | 28 |
| (2, 3) | 23 |
| (3, 3) | 1 |

In `beat_midi.txt`, column 2 marks a downbeat every 2 beats (144,061 of 148,499 gaps), and column 3 marks one every 4 beats (69,968 of 73,988 gaps). A song's typical spacing is (2, 4) in 880 songs and (3, 6) in 29. So the index labels duple metre in 2-beat measures, and column 3 holds the 4-beat bar lines.

**Revised rule** (same intent: simple metre, 4-beat bars, as in the paper's 4/4 data): keep a song if
- the index gives 2 beats per measure and 2 quavers per beat (simple duple metre), **and**
- at least 90% of the gaps between its column-3 downbeats are exactly 4 beats.

Column 3 then gives the 4/4 bar lines. The 90% steadiness check is new: it makes "steady 4 beats per bar" (the wording of the original proposal) measurable.

## Implementation notes (choices the rules did not cover)

**1. Very short notes (2026-10-27).** The rules did not say what happens to a note whose start and end round to the same sixteenth. The first audit run dropped those notes: 4.87% of melody notes in kept songs. That deletes real notes and leaves artificial gaps, which inflates the rest count of rule 11.

From the second run on, such a note is kept with a length of one sixteenth. It is still cut at the next onset, and the next onset is always later because same-sixteenth collisions are merged first. No rule threshold changed.

Two descriptive measurements were added to interpret rule 11: the unquantised gaps between notes, and the share of rests of at least one beat.

## Decisions after the audit (2026-11-06)

These were taken after the audit and before any model was trained on POP909. The files in `results/pop909_audit/` still show the rules as first written.

### Deviation 2: rule 11 (rests)

**What we found:** rule 11 measures articulation, not only rests. By the rule, 39.3% of melody notes are followed by a rest, far above the 5% threshold, so the pre-registered decision was "rest symbol". But:
- note onsets sit on the grid (median song: 100% within 20 ms), while note ends mostly do not (median song: 24%);
- 77% of the "rests" last exactly one sixteenth;
- only 3.4% of notes are followed by a gap of at least one beat.

Example, song 001: notes start every eighth note but sound for a sixteenth. That is detached singing, which the rule counts as a rest after every note.

**Revised rule:**
- a note's length is the time to the next onset (the inter-onset interval), which is reliable because onsets are on the grid;
- a gap of at least one beat (4 sixteenths) becomes a rest symbol with its own length, and the note before it keeps its sounding length;
- note ends are not modelled. They can still be reported as a separate articulation measure.

**Effect**, on the 335 songs of the pool below (a read-only check; the baseline's data step must reproduce these numbers):

| | Rule as written | Revised rule |
|---|---|---|
| Most common length | sixteenth, 45.7% | eighth, 48.8% |
| Rests per 100 notes | 39.0 | 3.4 |

This matches the paper's representation (note values that fill the bar, no rests) while keeping phrase breaks. **What is lost:** whether a note is sung detached or smooth. The paper did not model that either.

### Scope decision: the songs used (replaces the splitting branch of rule 16)

A large corpus is not a research aim of this project, so we use a small, uniform one. This was decided after seeing the song counts per group, and before seeing any model result.

- **Pool:** songs that passed rules 9, 10 and 15, and whose only key segment is major: 335 songs, 114,187 notes. Left out: 296 single-key minor songs and 114 songs that change key.
- **Why:** the paper's data is all in C major. One mode gives every song the same scale, and no song has to be cut apart.
- **Limitation:** the findings apply to major-key pop melodies.
- **Sample:** 100 songs, fixed now and not changed after seeing results. Sort the pool by song id and shuffle it with NumPy `default_rng(20261106)`. The first 80 songs are for training, the next 10 for validation, the last 10 for testing.

**Velocity:** rules 13 and 14 are not re-measured on this sample. Velocity stays relative to each song's median, with k = 39 bins requested. The bin edges come from the training songs only, and the number of levels that results is reported.

### Baseline setup

- **Track:** the MELODY track, final version.
- **Models:** three separate higher-order chains (pitch, length, velocity), each conditioned on its own last n values.
- **No chords.** This is the main difference from the paper, whose melody follows a chord plan. The brief defines the MDP state as the last notes, and the baseline has to share that state.
- **Key:** every song is moved to C major by the smallest transposition.
- **Length of output:** 8-bar pieces.
- **Bar lines:** as in the paper, a generated note or rest stays inside its bar. On the 335 songs of the pool, 4.0% of notes and 32.9% of rests cross a bar line, so this removes held notes across a bar line and long rests over one.
- **Pitch symbols:** actual notes (MIDI numbers after moving to C). The paper's contour-and-degree symbols exist to fit a melody to chords, which the baseline does not have, and decoding them loses leaps over an octave. After moving to C, 99.7% of notes fall in the C major scale (worst song 93.4%), which also supports the key labels.
- **Smoothing:** Witten–Bell, only when scoring held-out songs. Generation uses raw counts, as in the paper.

### Fixed in advance, measured on the sample

- **Rare lengths:** keep the most common lengths that together cover 99% of the training notes and rests. Any other length moves to the nearest kept length of the same kind (note or rest).
- **Memory length n:** for each chain, the n that best predicts the validation songs (bits per note). Results are reported for every n, as in the paper.

## Also reported (description only, no rule)

Songs and melody notes per song, length in bars, tempo range, pitch range, and the distribution of note durations in sixteenths.
