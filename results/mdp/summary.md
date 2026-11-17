# MDP results

Plan: `reports/mdp_plan.md`. Discussion: `reports/mdp_report.md`. 200 attempts per condition. * added after seeing the baseline's results.

Matched strengths: length 3.994, pitch 2.937, level 0.02787. Practice pieces for the main version: {'rhythm': 30000, 'pitch': 10000, 'loudness': 10000}; no leash: 30000.

## The rules

| | target (training songs) | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ends on C | 84% | 18% | 82% | 84% | 55% | 100% | 100% | 86% | 18% | 88% | 81% | 26% |
| ends on a long note | 79% | 4% | 76% | 80% | 38% | 100% | 100% | 5% | 76% | 77% | 86% | 10% |
| strong beats minus offbeats | 3.2 | -0.3 | 3.0 | 3.5 | 1.3 | 8.0 | 21.0 | 2.9 | 3.3 | -0.1 | 7.4 | -0.0 |

Targets: last notes of the training songs, and their loudness by beat (scripts/check_reward_rules.py).

## How far each policy moved from the baseline (KL, bits per piece)

| | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rhythm | 0.00 | 2.65 | 2.50 | 0.47 | 3.56 | 4.26 | 0.00 | 2.33 | 2.47 | 48.50 | - |
| pitch | 0.00 | 1.41 | 1.28 | 0.37 | 2.06 | 2.16 | 1.29 | 0.00 | 1.27 | 30.94 | - |
| loudness | 0.00 | 1.49 | 1.64 | 0.36 | 8.15 | 41.25 | 1.68 | 1.64 | 0.00 | 48.16 | - |
| choices the baseline rules out | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | - |

## Distance from the test songs (total variation, 0 = identical)

| statistic | real songs: mean (5th to 95th) | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pitch | 0.176 (0.112 to 0.263) | 0.109 | 0.114 | 0.116 | 0.118 | 0.115 | 0.115 | 0.107 | 0.118 | 0.112 | 0.154 | 0.120 |
| pitch class | 0.076 (0.043 to 0.108) | 0.060 | 0.062 | 0.058 | 0.055 | 0.055 | 0.055 | 0.055 | 0.068 | 0.058 | 0.101 | 0.071 |
| pitch step | 0.102 (0.065 to 0.152) | 0.074 | 0.092 | 0.076 | 0.083 | 0.077 | 0.080 | 0.083 | 0.082 | 0.083 | 0.252 | 0.086 |
| length | 0.133 (0.060 to 0.247) | 0.130 | 0.065 | 0.131 | 0.137 | 0.157 | 0.142 | 0.145 | 0.128 | 0.150 | 0.294 | 0.145 |
| length pair | 0.247 (0.172 to 0.369) | 0.219 | 0.185 | 0.226 | 0.235 | 0.252 | 0.236 | 0.239 | 0.221 | 0.250 | 0.446 | 0.239 |
| loudness | 0.205 (0.154 to 0.253) | 0.162 | 0.150 | 0.174 | 0.152 | 0.236 | 0.461 | 0.155 | 0.148 | 0.158 | 0.230 | 0.143 |
| loudness step | 0.129 (0.098 to 0.162) | 0.090 | 0.093 | 0.089 | 0.107 | 0.097 | 0.236 | 0.092 | 0.088 | 0.102 | 0.148 | 0.088 |

## Entropy (bits)

| statistic | test songs | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pitch | 3.98 | 3.92 | 3.81 | 3.88 | 3.91 | 3.92 | 3.91 | 3.90 | 3.96 | 3.91 | 4.21 | 3.94 |
| pitch class | 2.77 | 2.65 | 2.60 | 2.62 | 2.65 | 2.63 | 2.62 | 2.62 | 2.64 | 2.60 | 2.81 | 2.63 |
| pitch step | 3.43 | 3.37 | 3.28 | 3.37 | 3.35 | 3.37 | 3.32 | 3.36 | 3.32 | 3.34 | 4.08 | 3.34 |
| length | 2.43 | 2.10 | 2.24 | 2.15 | 2.12 | 2.19 | 2.20 | 2.09 | 2.14 | 2.16 | 3.34 | 2.09 |
| length pair | 4.58 | 3.88 | 4.05 | 3.90 | 3.86 | 3.95 | 3.97 | 3.84 | 3.88 | 3.91 | 6.33 | 3.86 |
| loudness | 4.39 | 4.43 | 4.44 | 4.47 | 4.43 | 4.40 | 3.80 | 4.45 | 4.46 | 4.43 | 4.55 | 4.46 |
| loudness step | 4.77 | 4.72 | 4.70 | 4.73 | 4.72 | 4.81 | 4.83 | 4.72 | 4.72 | 4.69 | 5.12 | 4.72 |

## Per piece: mean, and distance from real test excerpts (KS)

| feature | test excerpts | training excerpts | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| notes | 40.1 | 37.4 (0.13) | 48.3 (0.44) | 48.0 (0.41) | 46.1 (0.36) | 46.9 (0.37) | 44.1 (0.32) | 44.9 (0.35) | 47.8 (0.42) | 46.9 (0.37) | 45.5 (0.34) | 31.3 (0.50) | 47.8 (0.39) |
| distinct pitches | 8.5 | 7.4 (0.33) | 12.0 (0.76) | 11.8 (0.67) | 11.5 (0.65) | 11.8 (0.68) | 11.6 (0.62) | 11.7 (0.67) | 12.1 (0.71) | 12.1 (0.71) | 11.7 (0.62) | 12.9 (0.85) | 12.3 (0.73) |
| pitch range | 13.5 | 13.2 (0.11) | 22.6 (0.83) | 22.0 (0.74) | 21.8 (0.74) | 22.4 (0.78) | 21.8 (0.72) | 21.9 (0.76) | 23.0 (0.80) | 22.6 (0.75) | 22.2 (0.76) | 25.5 (0.89) | 23.5 (0.81) |
| mean step size | 2.4 | 2.4 (0.17) | 2.4 (0.09) | 2.3 (0.14) | 2.4 (0.12) | 2.4 (0.12) | 2.4 (0.12) | 2.4 (0.13) | 2.4 (0.11) | 2.3 (0.11) | 2.4 (0.09) | 3.9 (0.92) | 2.4 (0.11) |
| rests | 1.3 | 1.1 (0.15) | 0.9 (0.17) | 0.9 (0.21) | 0.8 (0.18) | 0.9 (0.21) | 0.9 (0.23) | 0.9 (0.13) | 1.1 (0.25) | 0.8 (0.17) | 0.8 (0.19) | 3.4 (0.65) | 1.0 (0.21) |
| loudness range | 20.2 | 17.5 (0.27) | 23.6 (0.48) | 23.9 (0.50) | 23.7 (0.50) | 23.7 (0.50) | 24.3 (0.56) | 24.7 (0.67) | 24.0 (0.53) | 23.7 (0.50) | 23.4 (0.46) | 23.9 (0.52) | 23.7 (0.51) |
| mean loudness step | 5.5 | 4.7 (0.19) | 5.0 (0.37) | 4.9 (0.37) | 5.1 (0.35) | 5.0 (0.35) | 5.6 (0.33) | 7.2 (0.45) | 5.0 (0.36) | 5.1 (0.32) | 4.9 (0.34) | 6.7 (0.44) | 5.1 (0.33) |
| rests between notes (corrected silence) | 8.5 | 6.9 | 5.8 | 5.4 | 5.2 | 5.6 | 5.2 | 4.6 | 6.3 | 4.4 | 5.3 | 20.0 | 5.7 |

## Copying from the training songs (longest copied run, share of the piece)

| view | real test excerpts | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| melody | 12% | 9% | 10% | 10% | 10% | 10% | 10% | 10% | 10% | 10% | 9% | 10% |
| pitch step | 21% | 15% | 16% | 16% | 16% | 17% | 16% | 15% | 16% | 16% | 16% | 16% |
| length | 30% | 26% | 25% | 27% | 28% | 28% | 27% | 27% | 27% | 28% | 17% | 30% |
| loudness | 14% | 10% | 10% | 11% | 11% | 12% | 13% | 10% | 11% | 11% | 13% | 10% |
| full copies (melody) | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% |

## Variety (4-gram overlap of random pairs, 0 = nothing shared)

| | real test excerpts | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unique pieces | 97% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
| melody | 0.019 | 0.001 | 0.000 | 0.001 | 0.001 | 0.000 | 0.000 | 0.001 | 0.001 | 0.001 | 0.000 | 0.001 |
| pitch step | 0.038 | 0.015 | 0.019 | 0.015 | 0.015 | 0.013 | 0.014 | 0.014 | 0.015 | 0.014 | 0.001 | 0.015 |
| length | 0.088 | 0.158 | 0.145 | 0.150 | 0.167 | 0.148 | 0.151 | 0.168 | 0.163 | 0.144 | 0.008 | 0.158 |
| loudness | 0.020 | 0.001 | 0.001 | 0.001 | 0.001 | 0.003 | 0.015 | 0.001 | 0.001 | 0.001 | 0.000 | 0.001 |

| | baseline | MDP main (practised) | MDP main (exact) | MDP 0.5x | MDP 2x | MDP 4x | MDP without long ending | MDP without ending on C | MDP without strong beats | no leash | baseline, rhythm memory 2* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pieces finished | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% | 100% |
