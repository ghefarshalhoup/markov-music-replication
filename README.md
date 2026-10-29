# Music generation with Markov models: a replication

A from-scratch Python reimplementation of **SuperWillow**, the music composition system in
W. Schulze and B. van der Merwe, ["Music Generation with Markov Models"](https://doi.org/10.1109/MMUL.2010.44),
*IEEE MultiMedia* 18(3), 2011, trained on the paper's own training pieces and checked
claim by claim against the paper.

Research module, M.Sc. Artificial Intelligence, BTU Cottbus-Senftenberg (phase 1: replication).

## Findings at a glance

- **The paper's worked examples are reproduced exactly**: the HMM in Table 1 / Figure 2,
  the 13-state prediction suffix automaton in Figure 1, and the melodic-arc encoding in
  Figure 4. Each is a unit test.
- **A typo in the paper**: in Figure 4 the 5th hidden symbol must be `+5`, not `+3`,
  by the paper's own definition of the encoding.
- **"Long memory" means copying**: at memory lengths of 6 and above, every piece the
  higher-order model manages to finish is a note-for-note copy of a training piece.
- **Mixed-order models stay original**: a prediction suffix automaton that keeps only
  contexts seen at least twice still writes new pieces at memory length 10
  (100 % success on the Burger style, about 90 % on Melted).
- **An open question answered**: the paper left "how much is copied from the training
  data" open. At short memory, the longest copied stretch is 11–29 % of a melody;
  the paper's own published pieces score 8–21 %, so they were most likely generated with
  short memory.

Of the paper's 11 claims, 8 are reproduced fully or partly and 1 is answered with a new
result; the 2 that need human listeners (the survey and the effect of smoothing) are not
tested yet, but the survey pieces are generated.
Full write-up: [`reports/replication_report.md`](reports/replication_report.md).

## How the system works

A piece is composed in steps, each with its own probabilistic model learned from the
training pieces:

1. **Chord durations**: a Markov chain over how long each chord lasts.
2. **Chord progression**: a Markov chain over Roman numerals (I, IV, V, ...).
3. **Rhythm**: a Markov chain over note values, constrained to fit the chord durations.
4. **Melody**: a hidden Markov model whose hidden states are melodic contour plus scale
   degree, and whose observations are the chords underneath.

Each Markov chain is either **higher-order** (a fixed memory of L previous symbols) or
**mixed-order** (a prediction suffix automaton learned with LearnPSA, which uses long
memory only where it changes the prediction). Sampling uses a "duration left" constraint so
every piece ends exactly at the requested length.

## Project layout

```
markov_music/
  theory.py       pitches, scale degrees, chord recognition, note values
  musicxml_io.py  read/write MusicXML, write MIDI
  analysis.py     score -> the paper's training sequences (chord durations, Roman numerals, rhythm, melodic arc)
  models.py       higher-order Markov chain and prediction suffix automaton (LearnPSA)
  hmm.py          melodic-arc HMM: sample a melody given the chords
  generate.py     the generation pipeline with the "duration left" constraint
  evaluate.py     copying, memory and feature statistics
scripts/run_replication.py    all experiments -> results/
scripts/audit_pop909.py       data audit for phase 2 (needs POP909, see data/README.md)
tests/test_paper_examples.py  the paper's worked examples (Figures 1, 2, 4; Table 1)
reports/replication_report.md what was replicated and how it compares with the paper
results/                      summary tables, raw numbers, generated example pieces
```

## Run it

Python 3.11+.

```bash
pip install -r requirements.txt
python -m pytest                                   # the paper's worked examples
python scripts/run_replication.py --attempts 200   # all experiments, about 5 minutes
```

The experiments write `results/summary.md`, `results/replication_results.json` and example
pieces in `results/examples/`: MusicXML to open in [MuseScore](https://musescore.org),
and MIDI to listen to. The examples in this repository are already generated, next to the
human training pieces for comparison (`*_human_*`).

## Data

The paper's training pieces and its own generated pieces come from the SuperWillow project
and are included in `data/raw/` so everything runs out of the box.
Sources and licenses: [`data/README.md`](data/README.md).

## Next: phase 2

Phase 2 extends the models to a larger, modern corpus (POP909, 909 pop songs). The data
audit is done: its decision rules were written down *before* any statistic was measured
([`reports/pop909_audit_rules.md`](reports/pop909_audit_rules.md)), and the results are
in [`results/pop909_audit/summary.md`](results/pop909_audit/summary.md).

## License

Code: MIT (see [`LICENSE`](LICENSE)). The music data in `data/raw/` keeps its original
license (see [`data/README.md`](data/README.md)).
