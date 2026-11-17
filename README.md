# Music generation with Markov models and reinforcement learning

Research module "Extension 10: Music Generation using a Markov Decision Process", M.Sc. Artificial Intelligence, BTU Cottbus-Senftenberg.

The work has three parts:
1. **Replication.** A from-scratch Python reimplementation of **SuperWillow**, from W. Schulze and B. van der Merwe, ["Music Generation with Markov Models"](https://doi.org/10.1109/MMUL.2010.44), *IEEE MultiMedia* 18(3), 2011. It is trained on the paper's own pieces and checked against the paper claim by claim.
2. **Baseline on real pop data.** n-th order Markov chains for note length, pitch and loudness, on 100 songs from [POP909](https://github.com/music-x-lab/POP909-Dataset).
3. **MDP extension.** Reinforcement learning on top of the baseline. The model learns to choose notes that earn points for musical rules, while a KL "leash" keeps it close to the data.

## Findings at a glance

**Replication** ([`reports/replication_report.md`](reports/replication_report.md))
- **The paper's worked examples are reproduced exactly:** Table 1 / Figure 2, Figure 1 and Figure 4. Each is a unit test.
- **The paper has a typo:** in Figure 4, the 5th hidden symbol must be `+5`.
- **"Long memory" means copying:** at memory 6 and above, every finished higher-order piece copies a training piece. Mixed-order models stay original.

**Baseline on POP909** ([`reports/baseline_report.md`](reports/baseline_report.md))
- **Memory of one note predicts new songs best,** for pitch, length and loudness alike.
- **The pieces match real songs on overall statistics.** Each piece, though, wanders too wide (22.6 semitones against 13.5) and has too little silence.
- **Longer memory narrows the range only by copying,** first loudness, then pitch.

**MDP** ([`reports/mdp_plan.md`](reports/mdp_plan.md), [`reports/mdp_report.md`](reports/mdp_report.md))

**Setup.**
- Three agents, one each for rhythm, pitch and loudness.
- Each sees the baseline's state plus a clock, and chooses the next value.
- Its score is rule points minus the KL divergence from the baseline's probabilities.
- It learns by soft Q-learning, checked against an exact backward calculation.
- The three rules were chosen by checking candidates on the training songs:
  - end on C;
  - end on a long note;
  - louder on strong beats.

**Results.**
- **The rules reach real-song levels:**

  | | Baseline | MDP | Real songs |
  |---|---|---|---|
  | Pieces ending on C | 18% | 82% | 84% |
  | Pieces ending on a long note | 4% | 76% | 79% |
  | Strong beats louder by (velocity) | −0.3 | 3.0 | 3.2 |

- **Every other statistic stays where the baseline had it,** including copying and variety.
- **The policy changes by 1.3–2.6 bits per piece, almost all of it at the ending.** The pitch agent starts heading for the final C a note or two early.
- **Pushing the rules past real songs, or removing the leash, breaks the music.** At 4× strength the loudness accent becomes mechanical. Without the leash the melody drifts toward random.
- **A listening test is planned:** [`reports/listening_test_plan.md`](reports/listening_test_plan.md).

## Project layout

```
markov_music/          the package
  theory.py            pitches, scale degrees, chords, note values
  musicxml_io.py       reading MusicXML, writing MusicXML and MIDI
  analysis.py          the paper's analysis: chord labelling, melodic contour
  models.py            higher-order Markov chains and prediction suffix automata (LearnPSA)
  hmm.py               the melody HMM: emissions and constrained sampling
  generate.py          the generation pipeline with the "duration left" constraint
  evaluate.py          copying, memory and feature statistics
  pop909.py            POP909: reading, clean-up, the song sample, lengths and loudness levels
  baseline.py          three separate chains on POP909, scoring, copying and variety
  mdp.py               the MDP: three agents on a leash, exact best behaviour, soft Q-learning
scripts/
  run_replication.py        the replication -> results/
  audit_pop909.py           POP909 measured against rules fixed in advance -> results/pop909_audit/
  run_baseline.py           the POP909 baseline -> results/baseline/
  check_reward_rules.py     candidate reward rules, checked on the training songs -> results/reward_rules/
  check_mdp_zero.py         with no rule points the MDP must be exactly the baseline -> results/mdp/
  fit_rule_strengths.py     rule strengths matched to the training songs, and the 0-4x sweep
  practise_agents.py        soft Q-learning practice, checked against the exact answers
  practise_without_leash.py the data only as starting point (no leash)
  run_mdp.py                every MDP condition, measured as the baseline was -> results/mdp/summary.md
tests/                 worked examples from the paper, the baseline and the MDP (57 tests)
reports/               plans (fixed before measuring) and reports
results/               summary tables, raw numbers, example pieces (MIDI / MusicXML)
```

## Run it

Python 3.11+.

```bash
pip install -r requirements.txt
python -m pytest
python scripts/run_replication.py --attempts 200      # about 5 minutes
# the rest needs POP909, see data/README.md
python -I scripts/audit_pop909.py
python -I scripts/run_baseline.py --attempts 200
python -I scripts/check_reward_rules.py
python -I scripts/check_mdp_zero.py
python -I scripts/fit_rule_strengths.py               # about 7 minutes
python -I scripts/practise_agents.py
python -I scripts/practise_without_leash.py           # about 4.5 minutes
python -I scripts/run_mdp.py
```

The MDP scripts run in this order, because each reads the files written by the ones before it.

**Listening.**
- `results/examples/`: the replication's pieces, with the human training pieces as `*_human_*`.
- `results/baseline/examples/`: baseline pieces and real POP909 excerpts.
- `results/mdp/examples/`: MDP pieces (`mdp_*`), pieces with the rules pushed too far (`mdp_4x_*`), and pieces without the leash (`no_leash_*`).

## Data

- **Included:** the paper's training pieces and its own generated pieces, in `data/raw/`.
- **Not included:** POP909 (MIT licence, about 40 MB). Download it as described in [`data/README.md`](data/README.md).

## License

Code: MIT (see [`LICENSE`](LICENSE)). The music data in `data/raw/` keeps its original license (see [`data/README.md`](data/README.md)).
