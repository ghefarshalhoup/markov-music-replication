# POP909 audit results

Rules: `reports/pop909_audit_rules.md`.

## Songs kept after each filter

| step | songs |
|---|---|
| all songs | 909 |
| after no melody | 909 |
| after metre (rule 10) | 855 |
| after timing grid (rule 9) | 746 |
| after constant velocity (rule 15) | 745 |
| units after splitting at key changes | 854 |

## Decisions

| rule | measured | decision |
|---|---|---|
| rule 9 timing grid | 109 of 855 songs below p16 = 0.95; median p16 = 1.000 | sixteenth grid; exclude 109 songs (13 of them would pass with triplets added) |
| rule 10 metre | 54 songs not simple duple or bars not steady | keep simple duple metre with steady 4-beat bars (deviation 1) |
| rule 11 rests | 39.3% of melody notes are followed by a rest (threshold 5%) | rest symbol with its own duration |
| rule 12 clean-up | simultaneous onsets 0.50%, overlapping notes 8.6% (median overlap 27 ms), same-sixteenth collisions 0.04%, shorter than half a sixteenth (lengthened to one) 4.87% | cut at the next onset; keep the highest of simultaneous notes (always applied) |
| rule 14 velocity reference | between-song share of velocity variance = 0.65 (threshold 0.5) | relative to each song's median |
| rule 13 velocity levels | H(V) = 4.95 bits; information kept: k=4: 40%, k=8: 60%, k=12: 71%, k=16: 74%, k=24: 85%, k=32: 88%, k=48: 91%, k=64: 92% | 26 levels (k = 39 bins requested; tied values merge), RMS error 1.28 velocity units |
| rule 15 constant velocity | 1 songs with one velocity value; 6 kept songs have a standard deviation below 2 | exclude only the constant ones |
| rule 16 key changes | 114 of 745 songs (15.3%) change key (threshold 10%); modes {'maj': 494, 'min': 360} | split songs at key changes |

## Description

- **units:** 854
- **melody notes:** 252850
- **notes per unit (median, min, max):** [309.0, 32, 839]
- **bars per unit (median, min, max):** [62.4375, 8.0, 186.625]
- **tempo bpm (5th, 50th, 95th percentile):** [58.0, 75.0, 123.0]
- **pitch (min, 1st pct, 99th pct, max):** [42, 56, 86, 96]
- **distinct durations:** 65
- **durations in sixteenths (share):** {'1': 0.4615, '2': 0.3108, '3': 0.075, '4': 0.0646, '6': 0.0184, '5': 0.0182, '8': 0.0118, '7': 0.0085, '10': 0.0058, '12': 0.0048, '9': 0.0047, '11': 0.0033}
- **rest lengths in sixteenths (share):** {'1': 0.7746, '2': 0.1007, '3': 0.0379, '4': 0.0239, '5': 0.013, '6': 0.011, '7': 0.0064, '8': 0.0057, '9': 0.0035, '10': 0.0032}
- **rests of at least one beat (share of rests):** 0.08675112300005047
- **rests of at least one bar (share of rests):** 0.012537223035380811
- **notes followed by a rest of at least one beat:** 0.03410371593199892
- **unquantised gaps between notes, in sixteenths (share):** {'<0.1': np.float64(0.319), '0.1-0.5': np.float64(0.2359), '0.5-1.5': np.float64(0.3545), '1.5-4': np.float64(0.0614), '>=4': np.float64(0.0292)}
- **note ends within 20 ms of a sixteenth (median over songs):** 0.24079320113314448
- **key tonics:** {'C': 94, 'B': 78, 'F': 78, 'G': 77, 'D': 74, 'A': 72, 'E': 72, 'Ab': 72, 'Db': 72, 'Bb': 58, 'Gb': 54, 'Eb': 53}
