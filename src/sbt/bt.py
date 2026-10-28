# src/sbt/bt.py
"""A tiny behavior-tree engine. Conditions are SPARQL ASK queries."""
from rdflib import Graph

from .kb import ask
from .world import ACTIONS, FAILURE, RUNNING, SUCCESS


class Node:
    def tick(self, g: Graph, robot: str) -> str:
        raise NotImplementedError


class Condition(Node):
    def __init__(self, query: str):
        self.query = query

    def tick(self, g, robot):
        return SUCCESS if ask(g, self.query) else FAILURE


class Action(Node):
    def __init__(self, name: str, arg: str):
        self.name, self.arg = name, arg.removeprefix("ex:")

    def tick(self, g, robot):
        func, _ = ACTIONS[self.name]
        return func(g, robot, self.arg)


class Sequence(Node):
    """Run children in order; stop at the first FAILURE. Remembers where it was."""
    def __init__(self, children: list[Node]):
        self.children, self.i = children, 0

    def tick(self, g, robot):
        while self.i < len(self.children):
            status = self.children[self.i].tick(g, robot)
            if status == RUNNING:
                return RUNNING
            if status == FAILURE:
                self.i = 0
                return FAILURE
            self.i += 1
        self.i = 0
        return SUCCESS


class Fallback(Node):
    """Try children in order; stop at the first SUCCESS. Remembers where it was."""
    def __init__(self, children: list[Node]):
        self.children, self.i = children, 0

    def tick(self, g, robot):
        while self.i < len(self.children):
            status = self.children[self.i].tick(g, robot)
            if status == RUNNING:
                return RUNNING
            if status == SUCCESS:
                self.i = 0
                return SUCCESS
            self.i += 1
        self.i = 0
        return FAILURE


def build(spec: dict) -> Node:
    """Turn the JSON tree (already validated) into Node objects."""
    kind = spec["type"]
    if kind == "sequence":
        return Sequence([build(c) for c in spec["children"]])
    if kind == "fallback":
        return Fallback([build(c) for c in spec["children"]])
    if kind == "condition":
        return Condition(spec["ask"])
    if kind == "action":
        return Action(spec["name"], spec["arg"])
    raise ValueError(f"unknown node type {kind}")


def run(g: Graph, trees: dict[str, Node], max_ticks: int = 60, on_tick=None) -> dict[str, str]:
    """Tick every robot's tree until all finish (or time runs out)."""
    status = {robot: RUNNING for robot in trees}
    for _ in range(max_ticks):
        for robot, tree in trees.items():
            if status[robot] == RUNNING:
                status[robot] = tree.tick(g, robot)
        if on_tick:
            on_tick(g)
        if RUNNING not in status.values():
            break
    return status