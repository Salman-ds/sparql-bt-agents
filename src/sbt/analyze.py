"""Analyse a results file: numbers per variant/level, and why each failed task failed.

Usage:  python -m sbt.analyze --model qwen2.5:3b
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from . import bt
from .kb import ask, load_kb, update
from .world import FAILURE

ROOT = Path(__file__).resolve().parents[2]


def leaf_failures(task: dict, trees: dict) -> tuple[dict, list[str]]:
    """Re-run the task and record every condition/action that returned FAILURE."""
    log = []
    orig_action, orig_cond = bt.Action.tick, bt.Condition.tick

    def action_tick(self, g, robot):
        status = orig_action(self, g, robot)
        if status == FAILURE:
            log.append(f"{robot}: action {self.name} ex:{self.arg} failed")
        return status

    def cond_tick(self, g, robot):
        status = orig_cond(self, g, robot)
        if status == FAILURE:
            log.append(f"{robot}: condition {self.query} was false")
        return status

    bt.Action.tick, bt.Condition.tick = action_tick, cond_tick
    try:
        g = load_kb()
        for q in task["setup"]:
            update(g, q)
        status = bt.run(g, {robot: bt.build(tree) for robot, tree in trees.items()})
        assert ask(g, task["goal"]) is False
    finally:
        bt.Action.tick, bt.Condition.tick = orig_action, orig_cond
    return status, log


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    args = parser.parse_args()
    tag = args.model.replace(":", "_")
    results = json.loads((ROOT / "results" / f"results_{tag}.json").read_text())
    tasks = {t["id"]: t for t in json.loads((ROOT / "tasks" / "tasks.json").read_text())}

    for variant, rows in results.items():
        print(f"\n=== {variant} ===")
        for level in (1, 2, 3, "all"):
            sub = [r for r in rows if level == "all" or r["level"] == level]
            print(f"level {level}: valid {sum(r['valid'] for r in sub)}/{len(sub)}  "
                  f"success {sum(r['success'] for r in sub)}/{len(sub)}  "
                  f"avg repairs {sum(r['repairs'] for r in sub) / len(sub):.2f}")
        first = Counter(e.split(" ")[0] for r in rows for p in r["plans"].values()
                        for e in p["history"][0]["errors"])
        print("validator errors at first attempt:", dict(first) or "none")
        fixed = sum(1 for r in rows for p in r["plans"].values()
                    if p["history"][0]["errors"] and not p["errors"])
        print("instructions fixed by repair:", fixed)

    d, r = results["direct"], results["repair"]
    same = all(a["plans"][k]["tree"] == b["plans"][k]["tree"] for a, b in zip(d, r) for k in a["plans"])
    print("\ndirect and repair produced identical trees:", same)

    print("\n=== failed tasks (direct) ===")
    for row in d:
        if row["success"]:
            continue
        trees = {robot: p["tree"] for robot, p in row["plans"].items()}
        status, log = leaf_failures(tasks[row["id"]], trees)
        print(f"\n{row['id']}  final status: {status}")
        for line in log:
            print("   ", line)


if __name__ == "__main__":
    main()
