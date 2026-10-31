# Failure analysis: qwen2.5:3b

All numbers come from `python -m sbt.analyze --variant direct` and `python -m sbt.analyze --variant grounded`. The "first failure" column comes from re-executing each generated tree in the simulation and logging every condition or action that returned `FAILURE`.

The direct and repair variants produced **identical trees**: every tree passed the validator at the first attempt, so the repair loop never ran. The table below therefore covers both variants.

# Part 1: Without grounding (direct / repair)

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

---

# Part 2: With state grounding (grounded / grounded_repair)

The prompt now also contains the current facts from the graph (`ex:isAt`, `ex:heldBy`, `ex:claimedBy`, `ex:status`), read after each task's setup. Again every tree passed the validator at the first attempt, so `grounded` and `grounded_repair` produced **identical trees**.

**Result:** 13/20 tasks succeeded (direct: 7/20). 19/26 instructions succeeded (direct: 13/26). No task went from success to failure.

## Per-task table (7 failed tasks out of 20)

| Task | Failing robot | First failure (re-executed) | Category | What went wrong | Without grounding |
|---|---|---|---|---|---|
| L2-03 | robotB | condition `shelf3 isAt robotA` false | Impossible condition | Subject and object are swapped and the wrong robot is named. Every IRI exists, but a shelf cannot be `isAt` a robot | wrong shelf |
| L2-05 | robotA | condition `redPackage isAt shelf1` false | Missing / misplaced backup plan | The facts say red is on `shelf2`, but the tree checks `shelf1` first in a plain sequence; the `shelf2` branch is a fallback placed after it (and there is no `claim`) | backup plan |
| L2-06 | robotB | `drop ex:greenPackage` failed | Wrong step order | Correctly chose `dock1` (the only free dock), but `move_to dock1 → drop` comes before `move_to shelf3 → pick` | wrong shelf |
| L2-07 | robotA | condition `redPackage claimedBy robotA` false | Missing / misplaced backup plan | The facts say red is claimed by robotB. The tree starts with a condition that is therefore false, and there is no fallback to the blue package at all | backup plan |
| L3-02 | robotB | `pick ex:greenPackage` failed | Missing step | Correct shelf (`shelf3`), but no `claim` before `pick`. robotA's plan succeeded | wrong shelf |
| L3-03 | robotB | `claim ex:redPackage` failed | Missing / misplaced backup plan | robotA claims red first; robotB's fallback to green comes after the failing claim in a sequence. robotA's plan succeeded | backup plan |
| L3-04 | robotB | `claim ex:bluePackage` failed | Missing / misplaced backup plan | robotA claims blue first; robotB has no fallback around its claim. robotA's plan succeeded | backup plan |

## Category counts: direct vs. grounded

| Category | direct | grounded | Catchable by the validator? |
|---|---|---|---|
| Invalid term / action / type | 0 | 0 | yes |
| Broken SPARQL / JSON / structure | 0 | 0 | yes |
| Wrong package location | 8 | **0** | no |
| Missing / misplaced backup plan | 4 | 4 | no |
| Missing step | 1 | 1 | no |
| Wrong step order | 0 | 1 | no |
| Impossible condition | 0 | 1 | no |
| **Total failed tasks** | **13** | **7** | |

## Task transitions

| Task | direct | grounded |
|---|---|---|
| L1-03, L1-05, L3-01, L3-05, L3-06 | wrong shelf | success |
| L1-07 | missing step | success |
| L2-03 | wrong shelf | impossible condition |
| L2-06 | wrong shelf | wrong step order |
| L3-02 | wrong shelf | missing step |
| L2-05, L2-07, L3-03, L3-04 | backup plan | backup plan |
| L1-01, L1-02, L1-04, L1-06, L2-01, L2-02, L2-04 | success | success |

## Package locations chosen by the model (grounded, all 26 instructions)

| Package | True location | Model's choice before `pick` |
|---|---|---|
| red | shelf1 (shelf2 in L2-05) | shelf1 (11×), shelf2 (1×) |
| blue | shelf2 | shelf2 (6×) |
| green | shelf3 | **shelf3 (9×)**, previously 0× |

## Observations

- Grounding removed every wrong-location error (8 → 0) and broke no task that worked before.
- Three tasks that failed on location now fail on a different logic error. Fixing the knowledge problem uncovered a structural one.
- The four backup-plan failures are the same tasks in both runs. Knowing the facts (e.g. "red is claimed by robotB" in L2-07) did not make the model build a fallback around the failing action.
- 23 of 26 grounded plans contain a `claim` (direct: 25 of 26). Grounding did not improve adherence to the claim-before-pick rule.
- The impossible condition in L2-03 (`ex:shelf3 ex:isAt ex:robotA`) could be caught symbolically by `rdfs:domain`/`rdfs:range` checks, which the current ontology does not declare.
