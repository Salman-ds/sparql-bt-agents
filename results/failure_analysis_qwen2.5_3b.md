# Failure analysis: qwen2.5:3b

All numbers come from `python -m sbt.analyze --model qwen2.5:3b`. The "first failure" column comes from re-executing each generated tree in the simulation and logging every condition or action that returned `FAILURE`.

The direct and repair variants produced **identical trees**: every tree passed the validator at the first attempt, so the repair loop never ran. The table below therefore covers both variants.

## Per-task table (13 failed tasks out of 20)

| Task | Failing robot | First failure (re-executed) | Category | What went wrong |
|---|---|---|---|---|
| L1-03 | robotB | `pick ex:greenPackage` failed | Wrong package location | Went to `shelf1`; the green package is on `shelf3` |
| L1-05 | robotA | condition `greenPackage isAt shelf1` false | Wrong package location | Checked `shelf1` for the green package (it is on `shelf3`) |
| L1-07 | robotA | `pick ex:redPackage` failed | Missing step | No `claim` before `pick`; the only one of 26 plans without a claim |
| L2-03 | robotB | `pick ex:greenPackage` failed | Wrong package location | Went to `shelf1`; the dock fallback (dock 3 → dock 2) itself was correct |
| L2-05 | robotA | condition `redPackage isAt shelf1` false | Missing / misplaced backup plan | Task says the package may be on shelf 1 or 2 (setup: shelf 2). The tree checks shelf 1 in a plain sequence with no fallback for shelf 2 |
| L2-06 | robotB | `pick ex:greenPackage` failed | Wrong package location | Went to `shelf1`; the three-dock fallback itself was correct |
| L2-07 | robotA | `claim ex:redPackage` failed | Missing / misplaced backup plan | Red is pre-claimed by robotB. The fallback to the blue package is placed *after* the failing claim inside the same sequence, so it is never reached. The red branch also has no `move_to shelf` or `pick` |
| L3-01 | robotB | condition `greenPackage isAt shelf1` false | Wrong package location | robotA's plan succeeded |
| L3-02 | robotB | `pick ex:greenPackage` failed | Wrong package location | robotA's plan succeeded |
| L3-03 | robotB | `claim ex:redPackage` failed | Missing / misplaced backup plan | robotA claims red first (as intended). robotB's fallback to green comes after the failing claim in a sequence, so it is never reached (it also points to `shelf2` for green) |
| L3-04 | robotB | `claim ex:bluePackage` failed | Missing / misplaced backup plan | Same pattern: robotA claims blue first and robotB has no fallback around its claim. robotA's plan succeeded |
| L3-05 | robotB | condition `greenPackage isAt shelf1` false | Wrong package location | robotA's plan succeeded, correctly falling back from busy dock 1 to dock 2 |
| L3-06 | robotA | condition `greenPackage isAt shelf1` false | Wrong package location | robotB's plan succeeded |

## Category counts

| Category | Count (direct) | Count (repair) | Catchable by the validator? |
|---|---|---|---|
| Invalid term / action / type | 0 | 0 | yes |
| Broken SPARQL / JSON / structure | 0 | 0 | yes |
| Wrong package location | 8 | 8 | no |
| Missing / misplaced backup plan | 4 | 4 | no |
| Missing step | 1 | 1 | no |
| **Total failed tasks** | **13** | **13** | |

## Package locations chosen by the model (all 26 instructions)

Which shelf the model sent the robot to before each `pick`:

| Package | True location | Model's choice |
|---|---|---|
| red | shelf1 | shelf1 (10×) |
| blue | shelf2 | shelf2 (6×) |
| green | shelf3 | **shelf1 (8×)**, shelf2 (1×), shelf3 (0×) |

The model never sent a robot to `shelf3` for the green package, even though the first few-shot example in the prompt shows exactly that. The prompt lists the vocabulary (which shelves exist) but not the current world state (which package is on which shelf), so the model had to infer locations.

## Observations

- **No validator errors at all:** 0 errors at the first attempt across 26 instructions. With the exact vocabulary in the prompt and Ollama's JSON mode, this model did not hallucinate IRIs, actions or argument types, and it did not break SPARQL or JSON.
- **All 13 failures are well-formed but wrong.** They are invisible to a syntax/ontology validator by design.
- **Level 3 (0/6) fails on one robot per task:** in each of the 6 two-robot tasks, exactly one robot's plan succeeded. Overall, 13 of 26 instructions executed successfully.
- **The model writes fallbacks correctly for busy docks** (L2-01, L2-02, L2-04 and robotA in L3-05 succeeded; L2-03 and L2-06 have correct dock fallbacks but fail on the shelf). It does **not** write correct fallbacks around a failing `claim` (L2-07, L3-03, L3-04) or for an uncertain package location (L2-05).
