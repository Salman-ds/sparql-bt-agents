# src/sbt/evaluate.py
"""Run every task with each variant and save the results.

Usage:  python -m sbt.evaluate --model qwen2.5:3b [--only L1-03] [--variants grounded repair]
New rows are merged into the existing results file, so partial runs keep earlier results.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from .bt import build, run
from .kb import ask, load_kb, update
from .planner import plan

ROOT = Path(__file__).resolve().parents[2]
# name -> (max_repairs, grounded)
VARIANTS = {
    "direct": (0, False),
    "repair": (2, False),
    "grounded": (0, True),
    "grounded_repair": (2, True),
}

def run_task(task: dict, model: str, max_repairs: int, grounded: bool) -> dict:
    g = load_kb()
    for q in task["setup"]:
        update(g, q)
    plans = {robot: plan(text, g, model, max_repairs, grounded) for robot, text in task["robots"].items()}
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
    lines = ["| Variant | Valid trees | Task success | Avg repairs |",
             "|---|---|---|---|"]
    for variant, rows in results.items():
        n = len(rows)
        lines.append(f"| {variant} | {sum(r['valid'] for r in rows)}/{n} | "
                     f"{sum(r['success'] for r in rows)}/{n} | "
                     f"{sum(r['repairs'] for r in rows) / n:.2f} |")

    # task success per level, one column per variant
    lines += ["", "| Level | " + " | ".join(results) + " |",
              "|---|" + "---|" * len(results)]
    for level in (1, 2, 3):
        cells = []
        for rows in results.values():
            sub = [r for r in rows if r["level"] == level]
            cells.append(f"{sum(r['success'] for r in sub)}/{len(sub)}" if sub else "-")
        lines.append(f"| L{level} | " + " | ".join(cells) + " |")
    lines += ["", "Remaining error types (after the last attempt):", ""]
    for variant, rows in results.items():
        kinds = Counter(e.split(" ")[0] for r in rows for e in r["errors"])
        lines.append(f"- {variant}: {dict(kinds) or 'none'}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--only", help="run a single task id, e.g. L1-01")
    parser.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=list(VARIANTS),
                        help="which variants to run (default: all)")
    args = parser.parse_args()

    all_tasks = json.loads((ROOT / "tasks" / "tasks.json").read_text())
    order = {t["id"]: i for i, t in enumerate(all_tasks)}
    tasks = [t for t in all_tasks if t["id"] == args.only] if args.only else all_tasks
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    tag = args.model.replace(":", "_")
    path = out / f"results_{tag}.json"
    results = json.loads(path.read_text()) if path.exists() else {}
    for variant in args.variants:
        max_repairs, grounded = VARIANTS[variant]
        rows = {r["id"]: r for r in results.get(variant, [])}
        for task in tasks:
            r = run_task(task, args.model, max_repairs, grounded)
            rows[r["id"]] = r
            print(f"{variant:15} {r['id']}  valid={r['valid']!s:5}  success={r['success']!s:5}  repairs={r['repairs']}")
        results[variant] = sorted(rows.values(), key=lambda r: order[r["id"]])

    path.write_text(json.dumps(results, indent=2))
    table = summarize(results)
    (out / f"summary_{tag}.md").write_text(f"# Results: {args.model}\n\n{table}\n")
    print("\n" + table)


if __name__ == "__main__":
    main()