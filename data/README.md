# Data

| Folder | What | Source |
|---|---|---|
| `raw/superwillow_styles/Burger` | 4 pieces by Eduard Burger: the paper's "Burger" style | [SuperWillow project](https://sourceforge.net/projects/superwillow/), `index_files/styles/` |
| `raw/superwillow_styles/Melted` | 2 by J. C. Dalton, 1 by affron5, 1 by MindAtrophy: the "Melted" style | same |
| `raw/superwillow_styles/Schulze` | 3 pieces by W. Schulze (not used in the paper's survey) | same |
| `raw/superwillow_demos` | the paper's own generated pieces b2, b4 (mixed), b5 (higher), m2, m4 (mixed), m5 (higher) | SuperWillow demo table |

The SuperWillow files are redistributed unchanged under the project's license
(GNU GPL v3 / Academic Free License, as listed on SourceForge). Credit for the pieces goes
to their composers and to W. Schulze and B. van der Merwe. Two Melted file names lost
their apostrophes so they could be saved on Windows.

## POP909 (phase 2, not included)

`scripts/audit_pop909.py` expects the [POP909 dataset](https://github.com/music-x-lab/POP909-Dataset)
with the contents of its `POP909/` folder copied into `raw/pop909/` (`raw/pop909/index.xlsx`,
`raw/pop909/001/001.mid`, ...). It is not included here because of its size (about 40 MB).
