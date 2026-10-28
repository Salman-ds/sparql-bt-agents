# src/sbt/world.py
"""The simulated warehouse. Every action reads and writes the RDF graph."""
from rdflib import Graph

from .kb import EX, ask, is_a, update

SUCCESS, FAILURE, RUNNING = "SUCCESS", "FAILURE", "RUNNING"


def _pos(g: Graph, name: str) -> tuple[int, int]:
    return int(g.value(EX[name], EX.x)), int(g.value(EX[name], EX.y))


def _place_at(g: Graph, x: int, y: int) -> str | None:
    for place in ("shelf1", "shelf2", "shelf3", "dock1", "dock2", "dock3"):
        if _pos(g, place) == (x, y):
            return place
    return None


def move_to(g: Graph, robot: str, place: str) -> str:
    """Move one grid step towards the place (x first, then y)."""
    if not is_a(g, place, "Place"):
        return FAILURE
    (rx, ry), (tx, ty) = _pos(g, robot), _pos(g, place)
    if (rx, ry) == (tx, ty):
        return SUCCESS
    if rx != tx:
        rx += 1 if tx > rx else -1
    else:
        ry += 1 if ty > ry else -1
    update(g, f"""
        DELETE {{ ex:{robot} ex:x ?x ; ex:y ?y . ex:{robot} ex:isAt ?p }}
        INSERT {{ ex:{robot} ex:x {rx} ; ex:y {ry} }}
        WHERE  {{ ex:{robot} ex:x ?x ; ex:y ?y . OPTIONAL {{ ex:{robot} ex:isAt ?p }} }}""")
    here = _place_at(g, rx, ry)
    if here:
        update(g, f"INSERT DATA {{ ex:{robot} ex:isAt ex:{here} }}")
    return SUCCESS if (rx, ry) == (tx, ty) else RUNNING


def claim(g: Graph, robot: str, package: str) -> str:
    """Reserve a package. Fails if another robot already claimed it."""
    if not is_a(g, package, "Package"):
        return FAILURE
    if ask(g, f"ASK {{ ex:{package} ex:claimedBy ?r FILTER(?r != ex:{robot}) }}"):
        return FAILURE
    update(g, f"INSERT DATA {{ ex:{package} ex:claimedBy ex:{robot} }}")
    return SUCCESS


def pick(g: Graph, robot: str, package: str) -> str:
    """Pick up a package: robot must be at its place, have claimed it, and hold nothing."""
    ok = is_a(g, package, "Package") and ask(g, f"""ASK {{
        ex:{robot} ex:isAt ?p . ex:{package} ex:isAt ?p .
        ex:{package} ex:claimedBy ex:{robot} .
        FILTER NOT EXISTS {{ ?other ex:heldBy ex:{robot} }} }}""")
    if not ok:
        return FAILURE
    update(g, f"""DELETE {{ ex:{package} ex:isAt ?p }}
                  INSERT {{ ex:{package} ex:heldBy ex:{robot} }}
                  WHERE  {{ ex:{package} ex:isAt ?p }}""")
    return SUCCESS


def drop(g: Graph, robot: str, package: str) -> str:
    """Put the package down where the robot stands. A dock must be free and becomes busy."""
    if not ask(g, f"ASK {{ ex:{package} ex:heldBy ex:{robot} . ex:{robot} ex:isAt ?p }}"):
        return FAILURE
    place = str(g.value(EX[robot], EX.isAt))[len(str(EX)):]
    if is_a(g, place, "Dock"):
        if not ask(g, f"ASK {{ ex:{place} ex:status ex:free }}"):
            return FAILURE
        update(g, f"DELETE DATA {{ ex:{place} ex:status ex:free }} ;"
                  f"INSERT DATA {{ ex:{place} ex:status ex:busy }}")
    update(g, f"DELETE DATA {{ ex:{package} ex:heldBy ex:{robot} }} ;"
              f"INSERT DATA {{ ex:{package} ex:isAt ex:{place} }}")
    return SUCCESS


# name -> (function, argument type). The validator uses this table too.
ACTIONS = {
    "move_to": (move_to, "Place"),
    "claim": (claim, "Package"),
    "pick": (pick, "Package"),
    "drop": (drop, "Package"),
}


def snapshot(g: Graph) -> dict:
    """Positions of robots and packages, for drawing the animation."""
    snap = {}
    for robot in ("robotA", "robotB"):
        snap[robot] = _pos(g, robot)
    for pkg in ("redPackage", "bluePackage", "greenPackage"):
        holder = g.value(EX[pkg], EX.heldBy)
        where = holder if holder is not None else g.value(EX[pkg], EX.isAt)
        snap[pkg] = _pos(g, str(where)[len(str(EX)):])
    return snap