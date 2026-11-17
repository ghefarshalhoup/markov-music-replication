# MDP report (Phase 2)

Extension 10: a Markov decision process (MDP) for note selection, compared with the POP909 baseline under the same conditions. The plan and every decision behind it are in `reports/mdp_plan.md`. All numbers come from `results/mdp/summary.md`, unless another file is named:
- 200 attempts per condition, with fixed seeds;
- 10 test songs, read for the first time in that run.

## Summary

- **The rules work.** At matched strength, pieces end on C 82% of the time and on a long note 76%, and strong beats are 3.0 velocity steps louder. The baseline: 18%, 4% and −0.3. The real training songs: 84%, 79% and 3.2.
- **Little else changes.** Every other statistic stays where the baseline had it, inside the range of real songs. Copying and variety don't change either.
- **The change is small and placed where it should be.**
  - Each agent's policy moves 1.3 to 2.6 bits per piece from the baseline.
  - Almost all of that is at the ending, and it starts a note or two early. The agent plans the ending; it does not just swap the last note.
- **Pushing harder costs realism, and loudness first.**
  - At 2× and 4× strength, every piece ends the same way, which real songs don't.
  - The loudness accent grows to 8 and then 21 velocity steps. At 4×, loudness leaves the range of real songs on every measure.
- **Without the leash, the music falls apart.** The rules are still reached, but steps, rhythms and rests drift toward random. The policy moves 30 to 48 bits per piece from the data, against 1.3 to 2.6 with the leash.
- **What the MDP does not fix.** The baseline's main weaknesses stay: too wide a pitch range (22 semitones against 13.5) and too little silence. No rule targets them, as the plan predicted.
- **Not yet done.** Nobody has listened yet.

## 1. What was built

- **Three agents, in the baseline's order: rhythm, pitch, loudness.** Each sees the baseline chain's state (its last value) plus a clock:
  - rhythm: time used;
  - pitch: notes left;
  - loudness: where the note starts.
- **Each agent's score:** rule points minus the KL divergence from the baseline's probabilities (the leash).
- **Two ways to find the best behaviour:**
  - **Exact:** worked backward from the end of the piece (`markov_music/mdp.py`, `Agent`).
  - **Practice:** soft Q-learning (`SoftQLearner`).
- **The three rules, fixed beforehand on the training songs** (`scripts/check_reward_rules.py`):
  - end on a long note (rhythm);
  - end on C (pitch);
  - louder on beats 1 and 3, softer off the beat (loudness).
- **Rule strengths:** each was set so that the agent follows its rule as often as the training songs do (`scripts/fit_rule_strengths.py`):
  - rhythm 3.99;
  - pitch 2.94;
  - loudness 0.0279 per velocity step.

**Checks.**
- All 57 tests pass.
- With no rule points, the MDP gives exactly the baseline: 1,200 of 1,200 pieces identical, and every probability identical (`results/mdp/zero_check.json`).
- Practice found one error in the exact calculation for loudness, which was then fixed. The exact version had averaged future weights instead of soft values, over the next note start that the rhythm decides.

## 2. The rules

| | Target (training songs) | Baseline | **MDP (practised)** | MDP (exact) |
|---|---|---|---|---|
| Ends on C | 84% | 18% | **82%** | 84% |
| Ends on a long note | 79% | 4% | **76%** | 80% |
| Strong beats minus offbeats (velocity) | 3.2 | −0.3 | **3.0** | 3.5 |

With 200 pieces, a rate is uncertain by about ±3 points. The 1,000-piece runs in `results/mdp/strengths.json` and `practice.json` give the same picture.

**Removing one rule** removes only that rule's effect. Without ending on C, pieces end on C 18% of the time; the other two rules are untouched. The agents are separate, so each rule acts only through its own agent. The long final C comes from two rules that act on the same last note.

## 3. How the policy changed

KL from the baseline's policy, in bits per piece, summed over the choices each piece made:

| | Rhythm | Pitch | Loudness |
|---|---|---|---|
| MDP (practised) | 2.65 | 1.41 | 1.49 |
| 0.5× | 0.47 | 0.37 | 0.36 |
| 2× | 3.56 | 2.06 | 8.15 |
| 4× | 4.26 | 2.16 | 41.25 |
| No leash | 48.50 | 30.94 | 48.16 |

**Where the change happens.** These were computed exactly for the matched strengths, in a scratch check on the exact agents (a 46-note piece for pitch).
- **Pitch:** 88% of the change is on the last note, 10% on the one before, and 2% earlier. On the second-to-last note, C rises from 22% to 29%, so the melody heads home before the final step.
- **Rhythm:** all of the change is in bar 8.

This is what reinforcement learning adds to the chain: looking ahead to a goal at the end of the piece. The rest of the piece keeps the baseline's choices.

**Rhythm and pitch saturate.** At 2× they are already at 99–100%, so 4× changes them little. The loudness rule has no ceiling, so its change keeps growing.

## 4. Resemblance, copying and variety

**Distance from the test songs** (total variation; "real range" means real songs, 5th to 95th percentile):
- **Leash versions (main, 0.5×, 2×, ablations):** every statistic stays inside the real range, close to the baseline.
- **4×:** loudness 0.461 and loudness step 0.236 fall outside (real ≤ 0.253 and ≤ 0.162).
- **No leash:** pitch step (0.252), length (0.294), length pair (0.446) and pitch class (0.101) all fall outside.

**Per piece**, as means:

| Feature | Test excerpts | Baseline | MDP (practised) | 4× | No leash |
|---|---|---|---|---|---|
| Notes | 40.1 | 48.3 | 48.0 | 44.9 | 31.3 |
| Pitch range (semitones) | 13.5 | 22.6 | 22.0 | 21.9 | 25.5 |
| Distinct pitches | 8.5 | 12.0 | 11.8 | 11.7 | 12.9 |
| Mean step size (semitones) | 2.4 | 2.4 | 2.3 | 2.4 | **3.9** |
| Rests between notes (sixteenths) | 8.5 | 5.8 | 5.4 | 4.6 | **20.0** |
| Mean loudness step (levels) | 5.5 | 5.0 | 4.9 | **7.2** | 6.7 |

- "Rests between notes" is the corrected silence measure from the plan: real and generated pieces are counted the same way.
- With the leash, the gap in silence stays (5.4 against 8.5) and the pitch range stays too wide (22.0 against 13.5). No rule addresses either.

**Copying.**
- The longest stretch copied from a training melody is 10% of the piece in every leash version, against 9% for the baseline and 12% for real test excerpts.
- No condition copies a whole melody.
- At 4×, loudness copying rises slightly (13%), and loudness patterns repeat more between pieces (pair overlap 0.015 against 0.001). This is the first sign of sameness.

**Variety.** All pieces are unique in every condition.
- **4×:** loudness entropy drops from 4.47 to 3.80 bits; loudness becomes less varied.
- **No leash:** entropy rises in every part, because the choices become more random. Pairs of pieces share almost no rhythm patterns (0.008 against 0.158 for the baseline).

## 5. Practice against the exact answer

The stop rule was fixed beforehand: on average, practice must be within 0.01 bits of the exact answer per choice.
- **Pieces needed:** rhythm 30,000, pitch 10,000, loudness 10,000.
- **Rule rates:** practice and the exact answer agree within chance (section 2).
- **Remaining difference, all in rhythm:**
  - At the stop, practice was still 0.37 bits per piece from the exact answer, and made about 1.5 more notes per piece (48.0 against 46.1).
  - A scratch check with more practice showed the gap closing: 46.7 notes after 100,000 pieces and 46.0 after 300,000 (0.02 bits per piece), against 45.8 for the exact answer.
  - So the remaining difference is unfinished practice, not a different answer.
  - The practised rhythm's length statistics sit slightly closer to the test songs (0.065 against 0.131), probably because the baseline's bar look-ahead isn't fully learned yet. This should not be read as an improvement.

## 6. Without the leash

`results/mdp/no_leash.json`; 500 pieces at each checkpoint.

| Practice pieces | 0 | 1,000 | 10,000 | 30,000 | 300,000 |
|---|---|---|---|---|---|
| Ends on C | 21% | 88% | 80% | 78% | 75% |
| Strong-beat gap (velocity) | −0.3 | 4.9 | 6.7 | 7.0 | 6.5 |
| Steps of 2 semitones or less (real 68%) | 67% | 47% | 45% | 41% | 35% |
| Pitch range (semitones) | 23.7 | 23.1 | 23.3 | 25.7 | 28.3 |
| Notes | 55.5 | 31.4 | 27.7 | 31.8 | 29.4 |

- **The rules are reached within 1,000 pieces.** The loudness accent overshoots, because nothing says when it is enough.
- **The data is forgotten steadily.** With only rule points, every choice that can still reach the points is worth the same, so the policy moves toward random among the continuations seen in training.
- **It turns random, not repetitive.** All pieces stay unique. Jaques et al. (2017) report repetition for their unleashed network instead. Our table can only choose continuations that occur in the training songs, so it drifts toward randomness.

## 7. Rhythm memory 2 (added after seeing the baseline)

- **Setup:** a baseline whose rhythm chain remembers two values instead of one.
- **Result:** almost the same as n = 1 (length distance 0.145 against 0.130; long endings 10% against 4%).
- **Conclusion:** longer rhythm memory does not supply the ending; the rule does.

## 8. Answers to the research questions

1. **Do the rewarded qualities improve?** Yes. The ending and the beat accent move from the baseline's levels to the real songs' levels.
2. **What does it cost?**
   - At matched strength, almost nothing measurable: resemblance, copying and variety stay at the baseline's levels.
   - The cost appears when the rules are pushed past real songs (2×, 4×), or when the leash is removed.
3. **How does the policy change?**
   - Slightly (1.3–2.6 bits per piece) and only near the end of the piece.
   - The pitch agent prepares the final C a note or two early.
   - The leash keeps everything else as the data had it.
4. **Do listeners hear a difference?** Not tested yet.

## 9. Limits

- **No listening test yet.**
- **Small loudness effect.** About 3 velocity steps; it may not be audible.
- **Uncertain targets.** The ending targets come from 80 song endings, and 200 pieces per condition give about ±3 points on each rate.
- **Real test excerpts can't check the rules.** They are cut at arbitrary bar lines, so their endings are not endings. Rule targets therefore come from the training songs' last notes.
- **Gaps that remain.** Pitch range and silence. The range variant (plan, option 2b) is the planned way to test the range.
- **Sweep and ablations used the exact answers,** not practised ones. Practice was shown to match the exact answer at 1×.

## 10. Listening files

In `results/mdp/examples/`:
- `mdp_1–5` (main);
- `mdp_4x_1–3`;
- `no_leash_1–3`;
- `baseline_1–3`.

Real test excerpts are in `results/baseline/examples/real_test_*.mid`.

Notes are held until the next note, as in the baseline, so these files are for a first impression, not yet for the listening test.

## Reproduce

These run in order. Each script reads the files written by the ones before it.

```bash
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -I scripts/check_reward_rules.py
.venv/Scripts/python.exe -I scripts/check_mdp_zero.py
.venv/Scripts/python.exe -I scripts/fit_rule_strengths.py      # about 7 minutes
.venv/Scripts/python.exe -I scripts/practise_agents.py
.venv/Scripts/python.exe -I scripts/practise_without_leash.py  # about 4.5 minutes
.venv/Scripts/python.exe -I scripts/run_mdp.py
```

If Windows blocks the venv's Python, see the README.
