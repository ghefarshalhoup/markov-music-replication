# POP909 baseline results

Plan: `reports/pop909_audit_rules.md`. Discussion: `reports/baseline_report.md`.

## Checks

| Check | Result |
|---|---|
| Reproduces the audit's numbers | yes (335 songs, 114187 notes) |
| Every chain beats no memory, which beats random | yes |
| ...and the 95% interval over test songs excludes zero | length: NO, pitch: yes, level: yes |
| Closer to the test songs than no memory (step statistics) | pitch step: yes, length pair: NO, loudness step: yes |
| Within the range of real songs (95th percentile) | pitch: yes, pitch class: yes, pitch step: yes, length: yes, length pair: yes, loudness: yes, loudness step: yes |
| Pieces that fully copy a training melody | 0% |
| Longest copied run, baseline vs real test excerpts | 9% vs 12% of the melody |
| Longest copied run for n = 1 to 8: melody | 9%, 10%, 11%, 11%, 12%, 11%, 11%, 12% |
| Longest copied run for n = 1 to 8: pitch step | 15%, 16%, 18%, 24%, 36%, 55%, 74%, 83% |
| Longest copied run for n = 1 to 8: length | 26%, 28%, 30%, 31%, 36%, 44%, 54%, 59% |
| Longest copied run for n = 1 to 8: loudness | 10%, 12%, 23%, 55%, 81%, 92%, 96%, 98% |

## Data

- Songs: 80 training, 10 validation, 10 test, from a pool of 335.
- Notes: 28268 training, 3219 validation, 3744 test.
- Lengths kept: 27 (N2, N1, N4, N3, N6, N8, R4, N5, N10, N12, N7, R5, N14, R6, N16, N9, R7, R8, N11, N13, R9, N18, R10, R11, N20, N17, R12).
- Loudness levels: 26. Reference velocity for MIDI: 93.
- Real 8-bar excerpts: 662 from training songs, 74 from test songs.

## Predicting held-out songs (bits per symbol, lower is better)

| n | length: validation | length: test | pitch: validation | pitch: test | level: validation | level: test |
|---|---|---|---|---|---|---|
| 0 | 2.499 | 2.476 | 4.136 | 4.078 | 4.404 | 4.504 |
| 1 |  **2.328 ** | 2.389 |  **2.785 ** | 2.906 |  **4.185 ** | 4.251 |
| 2 | 2.353 | 2.359 | 2.884 | 3.047 | 4.634 | 4.807 |
| 3 | 2.449 | 2.535 | 3.253 | 3.371 | 5.334 | 5.462 |
| 4 | 2.618 | 2.784 | 3.747 | 3.917 | 5.651 | 5.743 |
| 5 | 2.822 | 3.114 | 4.151 | 4.348 | 5.730 | 5.800 |
| 6 | 3.031 | 3.436 | 4.399 | 4.600 | 5.746 | 5.815 |
| 7 | 3.310 | 3.713 | 4.499 | 4.701 | 5.749 | 5.823 |
| 8 | 3.554 | 3.906 | 4.547 | 4.728 | 5.753 | 5.828 |

Bold: the n chosen on the validation songs. n = 0 is the no-memory reference.

| chain | symbols | random guess | no memory | chosen n | at chosen n | gain (95% interval over songs) | test songs improved |
|---|---|---|---|---|---|---|---|
| length | 27 | 4.807 | 2.476 | 1 | 2.389 | -0.088 (-0.182 to 0.025) | 7 of 10 |
| pitch | 37 | 5.248 | 4.078 | 1 | 2.906 | -1.173 (-1.526 to -0.863) | 10 of 10 |
| level | 26 | 4.755 | 4.504 | 1 | 4.251 | -0.253 (-0.361 to -0.136) | 9 of 10 |

All three chains together, bits per note on the test songs: random 14.96, no memory 11.14, chosen 9.62.

### How much the choice of n depends on chance and on the smoothing (validation songs only)

Resampled: how often each n wins when the validation songs are redrawn. Weight w: a fixed trust in the shorter context, instead of Witten-Bell; cells give the best n and its bits.

| chain | Witten-Bell | resampled | w=1 | w=3 | w=10 | w=30 | w=100 |
|---|---|---|---|---|---|---|---|
| length | n=1 (2.328) | n=1: 68%, n=2: 30%, n=3: 2% | n=1 (2.374) | n=1 (2.349) | n=2 (2.308) | n=2 (2.249) | n=3 (2.199) |
| pitch | n=1 (2.785) | n=1: 92%, n=2: 8% | n=1 (2.808) | n=1 (2.792) | n=1 (2.783) | n=2 (2.774) | n=2 (2.763) |
| level | n=1 (4.185) | n=1: 100% | n=1 (4.196) | n=1 (4.194) | n=1 (4.189) | n=1 (4.184) | n=1 (4.175) |

## Distance from the test songs (total variation, 0 = identical)

| statistic | real songs: mean (5th to 95th pct) | baseline | no memory | n=1 | n=2 | n=3 | n=4 | n=5 | n=6 | n=7 | n=8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pitch | 0.176 (0.112 to 0.263) | 0.109 | 0.107 | 0.106 | 0.115 | 0.139 | 0.146 | 0.171 | 0.183 | 0.176 | 0.155 |
| pitch class | 0.076 (0.043 to 0.108) | 0.060 | 0.059 | 0.056 | 0.059 | 0.060 | 0.066 | 0.085 | 0.078 | 0.077 | 0.088 |
| pitch step | 0.102 (0.065 to 0.152) | 0.074 | 0.510 | 0.080 | 0.079 | 0.079 | 0.084 | 0.090 | 0.088 | 0.095 | 0.101 |
| length | 0.133 (0.060 to 0.247) | 0.130 | 0.091 | 0.139 | 0.134 | 0.147 | 0.147 | 0.172 | 0.079 | 0.088 | 0.123 |
| length pair | 0.247 (0.172 to 0.369) | 0.219 | 0.218 | 0.233 | 0.226 | 0.243 | 0.248 | 0.276 | 0.181 | 0.198 | 0.223 |
| loudness | 0.205 (0.154 to 0.253) | 0.162 | 0.152 | 0.154 | 0.151 | 0.156 | 0.148 | 0.165 | 0.176 | 0.205 | 0.215 |
| loudness step | 0.129 (0.098 to 0.162) | 0.090 | 0.196 | 0.093 | 0.100 | 0.099 | 0.097 | 0.105 | 0.111 | 0.124 | 0.108 |

## Entropy (bits)

| statistic | test songs | baseline | no memory | n=1 | n=2 | n=3 | n=4 | n=5 | n=6 | n=7 | n=8 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pitch | 3.98 | 3.92 | 3.92 | 3.89 | 3.92 | 3.92 | 3.93 | 3.86 | 3.84 | 3.78 | 3.73 |
| pitch class | 2.77 | 2.65 | 2.65 | 2.63 | 2.63 | 2.63 | 2.62 | 2.61 | 2.61 | 2.61 | 2.59 |
| pitch step | 3.43 | 3.37 | 5.06 | 3.36 | 3.34 | 3.29 | 3.27 | 3.27 | 3.28 | 3.28 | 3.26 |
| length | 2.43 | 2.10 | 2.19 | 2.08 | 2.12 | 2.08 | 2.15 | 2.20 | 2.32 | 2.34 | 2.27 |
| length pair | 4.58 | 3.88 | 4.35 | 3.82 | 3.91 | 3.82 | 3.96 | 4.04 | 4.33 | 4.37 | 4.24 |
| loudness | 4.39 | 4.43 | 4.43 | 4.44 | 4.43 | 4.45 | 4.45 | 4.39 | 4.41 | 4.35 | 4.41 |
| loudness step | 4.77 | 4.72 | 5.17 | 4.71 | 4.67 | 4.67 | 4.65 | 4.60 | 4.63 | 4.58 | 4.67 |

## Per piece (8 bars): mean, and distance from real test excerpts (KS)

| feature | test excerpts | training excerpts | baseline | no memory | n=1 | n=2 | n=3 | n=4 | n=5 | n=6 | n=7 | n=8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| notes | 40.1 | 37.4 (0.13) | 48.3 (0.44) | 48.2 (0.45) | 48.5 (0.42) | 47.8 (0.41) | 47.8 (0.37) | 46.4 (0.30) | 43.5 (0.23) | 46.9 (0.26) | 45.7 (0.29) | 45.3 (0.29) |
| distinct pitches | 8.5 | 7.4 (0.33) | 12.0 (0.76) | 15.1 (0.97) | 12.0 (0.72) | 11.3 (0.55) | 10.8 (0.50) | 9.8 (0.34) | 9.1 (0.19) | 8.5 (0.14) | 7.8 (0.26) | 7.7 (0.28) |
| pitch range | 13.5 | 13.2 (0.11) | 22.6 (0.83) | 29.7 (1.00) | 22.5 (0.75) | 20.7 (0.65) | 19.7 (0.62) | 17.7 (0.47) | 16.5 (0.37) | 15.5 (0.28) | 14.1 (0.10) | 14.1 (0.15) |
| mean step size | 2.4 | 2.4 (0.17) | 2.4 (0.09) | 8.1 (1.00) | 2.4 (0.09) | 2.4 (0.11) | 2.3 (0.16) | 2.3 (0.21) | 2.3 (0.23) | 2.3 (0.18) | 2.3 (0.23) | 2.3 (0.19) |
| rests | 1.3 | 1.1 (0.15) | 0.9 (0.17) | 1.3 (0.27) | 0.9 (0.19) | 0.9 (0.24) | 1.0 (0.22) | 1.0 (0.16) | 0.9 (0.19) | 1.1 (0.28) | 1.1 (0.29) | 1.1 (0.25) |
| silent sixteenths | 20.8 | 22.2 (0.16) | 5.8 (0.33) | 8.3 (0.30) | 5.2 (0.39) | 5.5 (0.37) | 5.5 (0.37) | 5.4 (0.36) | 5.3 (0.36) | 6.3 (0.34) | 6.2 (0.39) | 6.4 (0.34) |
| loudness range | 20.2 | 17.5 (0.27) | 23.6 (0.48) | 24.3 (0.58) | 23.6 (0.48) | 23.0 (0.41) | 21.9 (0.24) | 20.0 (0.07) | 18.2 (0.27) | 18.5 (0.20) | 17.8 (0.29) | 18.3 (0.23) |
| mean loudness step | 5.5 | 4.7 (0.19) | 5.0 (0.37) | 7.0 (0.49) | 5.0 (0.33) | 4.8 (0.31) | 4.8 (0.27) | 4.7 (0.24) | 4.6 (0.26) | 4.7 (0.21) | 4.5 (0.25) | 4.9 (0.16) |

## Generation and copying

Copying compares each piece with the training songs. Real test excerpts are the natural level.

| setting | success | melody: longest run, share | melody: 4-gram overlap | full copies | pitch steps: longest share | lengths: longest share | loudness: longest share |
|---|---|---|---|---|---|---|---|
| real test excerpts | - | 12% | 11% | 0% | 21% | 30% | 14% |
| baseline | 100% | 9% | 10% | 0% | 15% | 26% | 10% |
| no memory | 100% | 6% | 0% | 0% | 9% | 20% | 9% |
| n=1 | 100% | 9% | 10% | 0% | 15% | 26% | 10% |
| n=2 | 100% | 10% | 13% | 0% | 16% | 28% | 12% |
| n=3 | 100% | 11% | 17% | 0% | 18% | 30% | 23% |
| n=4 | 100% | 11% | 17% | 0% | 24% | 31% | 55% |
| n=5 | 100% | 12% | 15% | 0% | 36% | 36% | 81% |
| n=6 | 100% | 11% | 11% | 0% | 55% | 44% | 92% |
| n=7 | 100% | 11% | 11% | 0% | 74% | 54% | 96% |
| n=8 | 100% | 12% | 14% | 0% | 83% | 59% | 98% |

## Variety between pieces

Unique: share of pieces that differ from all others. Overlap: 4-grams shared by random pairs, 0 = nothing shared.

| setting | unique pieces | unique melodies | overlap melody | overlap pitch steps | overlap lengths | overlap loudness |
|---|---|---|---|---|---|---|
| real test excerpts | 97% | 95% | 0.019 | 0.038 | 0.088 | 0.020 |
| baseline | 100% | 100% | 0.001 | 0.015 | 0.158 | 0.001 |
| no memory | 100% | 100% | 0.000 | 0.000 | 0.123 | 0.000 |
| n=1 | 100% | 100% | 0.001 | 0.014 | 0.172 | 0.001 |
| n=2 | 100% | 100% | 0.001 | 0.019 | 0.155 | 0.002 |
| n=3 | 100% | 100% | 0.001 | 0.023 | 0.145 | 0.004 |
| n=4 | 100% | 100% | 0.001 | 0.025 | 0.146 | 0.005 |
| n=5 | 100% | 100% | 0.001 | 0.024 | 0.124 | 0.012 |
| n=6 | 100% | 100% | 0.001 | 0.022 | 0.104 | 0.012 |
| n=7 | 100% | 100% | 0.000 | 0.022 | 0.106 | 0.008 |
| n=8 | 100% | 100% | 0.001 | 0.020 | 0.116 | 0.019 |

Size of each chain (contexts seen in training): baseline: length 28, pitch 38, level 27; no memory: length 1, pitch 1, level 1; n=1: length 28, pitch 38, level 27; n=2: length 323, pitch 298, level 695; n=3: length 1167, pitch 1293, level 5525; n=4: length 2540, pitch 3483, level 10024; n=5: length 4284, pitch 6352, level 11777; n=6: length 6184, pitch 8861, level 12419; n=7: length 8038, pitch 10522, level 12811; n=8: length 9690, pitch 11488, level 13139
