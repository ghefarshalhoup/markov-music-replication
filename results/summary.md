# Replication results (attempts per setting: 200)

## Burger

Training: 4 pieces, bars [9, 10, 13, 8], 216 melody notes; leaps over an octave: 1/212

### Success rate, 8 bars

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 100% | 100% | 100% |
| 2 | 100% | 100% | 100% |
| 3 | 100% | 100% | 100% |
| 4 | 63% | 62% | 100% |
| 5 | 42% | 38% | 100% |
| 6 | 0% | 1% | 100% |
| 7 | 1% | 2% | 100% |
| 8 | 1% | 0% | 100% |
| 9 | 1% | 0% | 100% |
| 10 | 0% | 0% | 100% |

### Best success rate over lengths 7-10 bars

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 100% | 100% | 100% |
| 2 | 100% | 100% | 100% |
| 3 | 100% | 100% | 100% |
| 4 | 63% | 62% | 100% |
| 5 | 42% | 38% | 100% |
| 6 | 2% | 4% | 100% |
| 7 | 11% | 3% | 100% |
| 8 | 4% | 4% | 100% |
| 9 | 4% | 6% | 100% |
| 10 | 9% | 6% | 100% |

### Failed step, 8 bars (counts)

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | - | - | - |
| 2 | - | - | - |
| 3 | - | - | - |
| 4 | chord progression 43, melody 31 | chord progression 32, melody 43 | - |
| 5 | melody 55, chord progression 62 | chord progression 60, melody 65 | - |
| 6 | chord progression 27, melody 172 | chord progression 28, melody 170 | - |
| 7 | melody 198 | melody 197 | - |
| 8 | melody 198 | melody 200 | - |
| 9 | melody 198 | melody 199 | - |
| 10 | melody 200 | melody 199 | - |

### Copying from training (8 bars): mean longest copied run as share of the melody / share verbatim

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 11% / 0% | 11% / 0% | 11% / 0% |
| 2 | 15% / 0% | 16% / 0% | 14% / 0% |
| 3 | 19% / 0% | 17% / 0% | 13% / 0% |
| 4 | 29% / 0% | 27% / 0% | 14% / 0% |
| 5 | 25% / 0% | 24% / 0% | 13% / 0% |
| 6 | 100% / 100% | 100% / 100% | 14% / 0% |
| 7 | 100% / 100% | 100% / 100% | 14% / 0% |
| 8 | 100% / 100% | - | 15% / 0% |
| 9 | 100% / 100% | 100% / 100% | 14% / 0% |
| 10 | - | 100% / 100% | 15% / 0% |

Paper's published pieces: b2 (mixed, 9 bars): longest run 8%, 4-gram overlap 13%; b4 (mixed, 7 bars): longest run 21%, 4-gram overlap 29%; b5 (higher, 8 bars): longest run 11%, 4-gram overlap 20%

### Memory actually used by the melody model (mean / max)

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 1.0 / 1 | 1.0 / 1 | 1.0 / 1 |
| 2 | 1.9 / 2 | 1.9 / 2 | 1.7 / 2 |
| 3 | 2.9 / 3 | 2.6 / 3 | 2.2 / 3 |
| 4 | 3.7 / 4 | 3.1 / 4 | 2.4 / 4 |
| 5 | 4.7 / 5 | 3.5 / 5 | 2.6 / 5 |
| 6 | 5.5 / 6 | 3.6 / 6 | 2.5 / 6 |
| 7 | 6.4 / 7 | 3.6 / 6 | 2.7 / 7 |
| 8 | 7.2 / 8 | - | 2.7 / 8 |
| 9 | 8.0 / 9 | 3.6 / 6 | 2.8 / 9 |
| 10 | - | 3.6 / 6 | 2.7 / 9 |

### Features: training vs paper's pieces vs ours (8 bars)

| set | notes/bar | ends on tonic | ends on I | mean abs interval | TV durations | TV numerals |
|---|---|---|---|---|---|---|
| training | 5.5 | 100% | 100% | 2.3 | 0.00 | 0.00 |
| paper (demos) | 7.7 | 100% | 100% | 2.3 | 0.21 | 0.15 |
| ours higher L=1 | 6.2 | 100% | 100% | 2.0 | 0.04 | 0.05 |
| ours higher L=2 | 5.2 | 100% | 100% | 2.0 | 0.05 | 0.06 |
| ours higher L=3 | 5.1 | 100% | 100% | 2.1 | 0.05 | 0.08 |
| ours higher L=5 | 6.1 | 100% | 100% | 1.9 | 0.23 | 0.16 |
| ours mixed L=1 | 6.6 | 100% | 100% | 1.9 | 0.10 | 0.06 |
| ours mixed L=2 | 5.1 | 100% | 100% | 2.1 | 0.03 | 0.07 |
| ours mixed L=3 | 5.4 | 100% | 100% | 2.1 | 0.04 | 0.07 |
| ours mixed L=5 | 5.5 | 100% | 100% | 1.9 | 0.14 | 0.15 |

## Melted

Training: 4 pieces, bars [9, 8, 8, 17], 223 melody notes; leaps over an octave: 1/219

### Success rate, 8 bars

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 100% | 100% | 98% |
| 2 | 54% | 54% | 91% |
| 3 | 8% | 6% | 90% |
| 4 | 0% | 0% | 93% |
| 5 | 0% | 0% | 88% |
| 6 | 0% | 0% | 90% |
| 7 | 18% | 12% | 88% |
| 8 | 31% | 37% | 87% |
| 9 | 56% | 44% | 91% |
| 10 | 50% | 50% | 90% |

### Best success rate over lengths 7-10 bars

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 100% | 100% | 98% |
| 2 | 99% | 100% | 96% |
| 3 | 96% | 96% | 92% |
| 4 | 18% | 14% | 93% |
| 5 | 5% | 4% | 94% |
| 6 | 2% | 2% | 94% |
| 7 | 18% | 12% | 92% |
| 8 | 44% | 38% | 96% |
| 9 | 76% | 76% | 92% |
| 10 | 82% | 79% | 92% |

### Failed step, 8 bars (counts)

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | - | - | melody 5 |
| 2 | melody 93 | melody 93 | melody 18 |
| 3 | melody 117, chord progression 67 | chord progression 75, melody 112 | melody 20 |
| 4 | melody 188, chord progression 11 | melody 192, chord progression 8 | melody 14 |
| 5 | melody 200 | melody 200 | melody 23 |
| 6 | melody 200 | melody 200 | melody 21 |
| 7 | melody 163 | melody 177 | melody 24 |
| 8 | melody 138 | melody 126 | melody 26 |
| 9 | melody 88 | melody 113 | melody 18 |
| 10 | melody 100 | melody 101 | melody 19 |

### Copying from training (8 bars): mean longest copied run as share of the melody / share verbatim

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 12% / 0% | 13% / 0% | 13% / 0% |
| 2 | 11% / 0% | 11% / 0% | 14% / 0% |
| 3 | 13% / 0% | 13% / 0% | 13% / 0% |
| 4 | 23% / 0% | - | 14% / 0% |
| 5 | - | - | 13% / 0% |
| 6 | - | - | 16% / 0% |
| 7 | 100% / 100% | 100% / 100% | 17% / 0% |
| 8 | 100% / 100% | 100% / 100% | 20% / 0% |
| 9 | 100% / 100% | 100% / 100% | 19% / 0% |
| 10 | 100% / 100% | 100% / 100% | 21% / 0% |

Paper's published pieces: m2 (mixed, 10 bars): longest run 10%, 4-gram overlap 7%; m4 (mixed, 10 bars): longest run 9%, 4-gram overlap 11%; m5 (higher, 9 bars): longest run 9%, 4-gram overlap 10%

### Memory actually used by the melody model (mean / max)

| L | higher | mixed | mixed_min_count2 |
|---|---|---|---|
| 1 | 1.0 / 1 | 1.0 / 1 | 1.0 / 1 |
| 2 | 1.9 / 2 | 1.9 / 2 | 1.7 / 2 |
| 3 | 2.9 / 3 | 2.5 / 3 | 2.1 / 3 |
| 4 | 3.7 / 4 | - | 2.3 / 4 |
| 5 | - | - | 2.4 / 5 |
| 6 | - | - | 2.4 / 5 |
| 7 | 6.2 / 7 | 3.4 / 6 | 2.4 / 5 |
| 8 | 7.0 / 8 | 3.2 / 6 | 2.4 / 5 |
| 9 | 7.8 / 9 | 3.8 / 9 | 2.4 / 5 |
| 10 | 8.5 / 10 | 3.8 / 9 | 2.4 / 5 |

### Features: training vs paper's pieces vs ours (8 bars)

| set | notes/bar | ends on tonic | ends on I | mean abs interval | TV durations | TV numerals |
|---|---|---|---|---|---|---|
| training | 5.1 | 50% | 50% | 2.1 | 0.00 | 0.00 |
| paper (demos) | 5.9 | 67% | 67% | 2.3 | 0.06 | 0.22 |
| ours higher L=1 | 5.1 | 75% | 53% | 1.3 | 0.06 | 0.03 |
| ours higher L=2 | 5.3 | 59% | 40% | 2.1 | 0.02 | 0.04 |
| ours higher L=3 | 5.1 | 75% | 100% | 2.3 | 0.02 | 0.36 |
| ours mixed L=1 | 5.2 | 74% | 52% | 1.3 | 0.05 | 0.03 |
| ours mixed L=2 | 5.4 | 56% | 47% | 2.0 | 0.04 | 0.03 |
| ours mixed L=3 | 5.2 | 77% | 100% | 2.2 | 0.06 | 0.41 |
