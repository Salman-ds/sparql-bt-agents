# src/sbt/render.py
"""Draw the warehouse and save an animated GIF of a run.

Usage:  python -m sbt.render     (runs the two-robot demo with hand-written trees)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

from .bt import build, run
from .kb import load_kb
from .world import snapshot

ROOT = Path(__file__).resolve().parents[2]
PLACES = {"shelf1": (0, 5), "shelf2": (2, 5), "shelf3": (4, 5),
          "dock1": (0, 0), "dock2": (2, 0), "dock3": (4, 0)}
COLORS = {"redPackage": "red", "bluePackage": "blue", "greenPackage": "green"}


def save_gif(frames: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4, 4))

    def draw(i):
        ax.clear()
        ax.set_xlim(-0.5, 5.5); ax.set_ylim(-0.5, 5.5)
        ax.set_xticks(range(6)); ax.set_yticks(range(6)); ax.grid(True)
        ax.set_title(f"tick {i}")
        for name, (x, y) in PLACES.items():
            ax.add_patch(plt.Rectangle((x - 0.45, y - 0.45), 0.9, 0.9,
                         color="tan" if "shelf" in name else "lightgrey"))
            ax.text(x, y - 0.38, name, ha="center", fontsize=6)
        snap = frames[i]
        for robot in ("robotA", "robotB"):
            x, y = snap[robot]
            ax.plot(x, y, "s", color="black", markersize=16)
            ax.text(x, y, robot[-1], color="white", ha="center", va="center", fontsize=9)
        for pkg, color in COLORS.items():
            x, y = snap[pkg]
            ax.plot(x + 0.25, y + 0.25, "o", color=color, markersize=8)

    FuncAnimation(fig, draw, frames=len(frames)).save(path, writer=PillowWriter(fps=3))
    plt.close(fig)


def demo():
    g = load_kb()
    deliver = lambda pkg, shelf, dock: {"type": "sequence", "children": [
        {"type": "action", "name": "claim", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{shelf}"},
        {"type": "action", "name": "pick", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{dock}"},
        {"type": "action", "name": "drop", "arg": f"ex:{pkg}"}]}
    trees = {"robotA": build(deliver("redPackage", "shelf1", "dock1")),
             "robotB": build(deliver("greenPackage", "shelf3", "dock3"))}
    frames = [snapshot(g)]
    run(g, trees, on_tick=lambda g: frames.append(snapshot(g)))
    (ROOT / "results").mkdir(exist_ok=True)
    save_gif(frames, ROOT / "results" / "demo.gif")
    print(f"saved results/demo.gif ({len(frames)} frames)")


if __name__ == "__main__":
    demo()