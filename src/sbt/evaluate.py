# src/sbt/evaluate.py
"""Run every task with two variants (direct vs. validate+repair) and save the results.

Usage:  python -m sbt.evaluate --model qwen2.5:3b
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from .bt import build, run
from .kb import ask, load_kb, update
from .planner import plan

ROOT = Path(__file__).resolve().parents[2]
VARIANTS = {"direct": 0, "repair": 2}


def run_task(task: dict, model: str, max_repairs: int) -> dict:
    g = load_kb()
    for q in task["setup"]:
        update(g, q)
    plans = {robot: plan(text, g, model, max_repairs) for robot, text in task["robots"].items()}
    valid = all(not p["errors"] for p in plans.values())
    success = False
    if valid:
        trees = {robot: build(p["tree"]) for robot, p in plans.items()}
        run(g, trees)
        success = ask(g, task["goal"])
    return {
        "id": task["id"], "level": task["level"], "valid": valid, "success": success,
        "repairs": sum(p["repairs"] for p in plans.values()),
        "errors": [e for p in plans.values() for e in p["errors"]],
        "plans": plans,
    }


def summarize(results: dict) -> str:
    lines = ["| Variant | Level | Valid trees | Task success | Avg repairs |",
             "|---|---|---|---|---|"]
    for variant, rows in results.items():
        for level in (1, 2, 3, "all"):
            sub = [r for r in rows if level == "all" or r["level"] == level]
            n = len(sub)
            if n == 0:
                continue
            lines.append(f"| {variant} | {level} | {sum(r['valid'] for r in sub)}/{n} | "
                         f"{sum(r['success'] for r in sub)}/{n} | "
                         f"{sum(r['repairs'] for r in sub) / n:.2f} |")
    lines += ["", "Remaining error types (after the last attempt):", ""]
    for variant, rows in results.items():
        kinds = Counter(e.split(" ")[0] for r in rows for e in r["errors"])
        lines.append(f"- {variant}: {dict(kinds) or 'none'}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--only", help="run a single task id, e.g. L1-01")
    args = parser.parse_args()

    tasks = json.loads((ROOT / "tasks" / "tasks.json").read_text())
    if args.only:
        tasks = [t for t in tasks if t["id"] == args.only]
    results = {}
    for variant, max_repairs in VARIANTS.items():
        results[variant] = []
        for task in tasks:
            r = run_task(task, args.model, max_repairs)
            results[variant].append(r)
            print(f"{variant:6} {r['id']}  valid={r['valid']!s:5}  success={r['success']!s:5}  repairs={r['repairs']}")

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    tag = args.model.replace(":", "_")
    (out / f"results_{tag}.json").write_text(json.dumps(results, indent=2))
    table = summarize(results)
    (out / f"summary_{tag}.md").write_text(f"# Results: {args.model}\n\n{table}\n")
    print("\n" + table)


if __name__ == "__main__":
    main()