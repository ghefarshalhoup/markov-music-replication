# Listening test clips

Made by `scripts/make_listening_clips.py`, following `reports/listening_test_plan.md`.
All clips: 90 beats per minute, MuseScore 4 piano, -23 LUFS, 1 s of silence at the end.

## Do the chosen clips represent their condition?

| | Real (10 clips) | Baseline (10) | MDP (10) | Baseline, all 200 | MDP, all 200 |
|---|---|---|---|---|---|
| ends on C | 80% | 30% | 90% | 18% | 82% |
| ends on a long note | 70% | 0% | 70% | 4% | 76% |
| strong beats minus offbeats | +2.6 | +0.1 | +2.1 | -0.3 | +3.0 |

Real clips end at a phrase end by construction, so they are expected to end well.

## Phrase-end excerpts available per test song

| Test song | Excerpts that end at a phrase end |
|---|---|
| 312 | 3 |
| 796 | 3 |
| 340 | 3 |
| 046 | 2 |
| 155 | 1 |
| 339 | 2 |
| 743 | 4 |
| 612 | 1 |
| 628 | 2 |
| 218 | 2 |

## Clips

| Id | Condition | Group | Source | Notes | Seconds | Gain (dB) | Peak (dBFS) | Ends on C | Ends long |
|---|---|---|---|---|---|---|---|---|---|
| 8de66c | real 1 | 1 | song 312, bars [82, 89] | 48 | 22.33 | -0.3 | -11.9 | yes | no |
| 7c53f8 | real 2 | 1 | song 796, bars [61, 68] | 29 | 22.33 | +0.3 | -10.2 | yes | yes |
| 68e7de | real 3 | 1 | song 340, bars [57, 64] | 40 | 22.33 | +3.2 | -10.2 | no | yes |
| 002469 | real 4 | 1 | song 046, bars [103, 110] | 25 | 21.67 | -0.1 | -10.6 | yes | yes |
| 50c1d6 | real 5 | 1 | song 155, bars [54, 61] | 43 | 22.33 | +0.1 | -9.8 | no | yes |
| 28640e | real 6 | 2 | song 339, bars [33, 40] | 45 | 22.33 | -0.2 | -12.4 | yes | no |
| 12644c | real 7 | 2 | song 743, bars [38, 45] | 69 | 22.33 | -1.7 | -10.0 | yes | no |
| 18e098 | real 8 | 2 | song 612, bars [56, 63] | 67 | 22.33 | -0.9 | -11.2 | yes | yes |
| dd1c84 | real 9 | 2 | song 628, bars [96, 103] | 28 | 22.33 | +2.3 | -9.8 | yes | yes |
| 9a9c7f | real 10 | 2 | song 218, bars [81, 88] | 42 | 22.33 | +0.5 | -11.0 | yes | yes |
| fe4358 | baseline 1 | 1 | evaluation piece 1 | 44 | 22.33 | +0.2 | -9.8 | no | no |
| 8525c4 | baseline 2 | 1 | evaluation piece 2 | 52 | 22.33 | +0.0 | -10.4 | yes | no |
| c9ea95 | baseline 3 | 1 | evaluation piece 3 | 45 | 22.33 | +0.6 | -10.8 | yes | no |
| cbf95b | baseline 4 | 1 | evaluation piece 4 | 44 | 22.33 | +1.3 | -9.7 | no | no |
| 6c8895 | baseline 5 | 1 | evaluation piece 5 | 58 | 22.33 | -0.2 | -10.6 | no | no |
| cf58c8 | baseline 6 | 2 | evaluation piece 6 | 53 | 22.33 | +0.6 | -9.1 | no | no |
| 5919de | baseline 7 | 2 | evaluation piece 7 | 41 | 22.33 | +1.2 | -9.7 | no | no |
| 207fa9 | baseline 8 | 2 | evaluation piece 8 | 41 | 22.33 | +0.9 | -10.1 | yes | no |
| a81604 | baseline 9 | 2 | evaluation piece 9 | 56 | 22.33 | +1.1 | -9.8 | no | no |
| 9415d7 | baseline 10 | 2 | evaluation piece 10 | 48 | 22.33 | -0.2 | -8.8 | no | no |
| 40d1c5 | MDP 1 | 1 | evaluation piece 1 | 51 | 22.33 | +0.4 | -10.5 | yes | no |
| 93f455 | MDP 2 | 1 | evaluation piece 2 | 46 | 22.33 | +1.0 | -8.9 | no | yes |
| cb6142 | MDP 3 | 1 | evaluation piece 3 | 52 | 22.33 | +1.6 | -9.4 | yes | no |
| 823ac4 | MDP 4 | 1 | evaluation piece 4 | 52 | 22.33 | -0.2 | -10.6 | yes | yes |
| 7de4b6 | MDP 5 | 1 | evaluation piece 5 | 55 | 22.33 | +0.4 | -10.2 | yes | yes |
| 6245ce | MDP 6 | 2 | evaluation piece 6 | 48 | 22.33 | +0.7 | -10.2 | yes | yes |
| eeb42a | MDP 7 | 2 | evaluation piece 7 | 38 | 22.33 | +1.7 | -9.7 | yes | yes |
| e16948 | MDP 8 | 2 | evaluation piece 8 | 43 | 22.33 | +1.2 | -9.8 | yes | yes |
| 9c2dc4 | MDP 9 | 2 | evaluation piece 9 | 44 | 22.33 | +0.4 | -10.0 | yes | yes |
| 2883c8 | MDP 10 | 2 | evaluation piece 10 | 43 | 22.33 | +2.0 | -7.2 | yes | no |
| d2eba5 | practice  |  | song 639, bars [104, 111] | 41 | 22.33 | +1.1 | -10.8 |  |  |
| 255860 | attention  |  | clip repeated note | 32 | 22.33 | +0.7 | -12.6 |  |  |
| 77f3af | attention  |  | clip C major scale | 29 | 22.33 | +3.2 | -9.9 |  |  |
