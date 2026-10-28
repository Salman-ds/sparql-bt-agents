# tests/test_core.py
from sbt.bt import build, run
from sbt.kb import ask, load_kb, update
from sbt.world import FAILURE, SUCCESS, claim, pick


def deliver(pkg, shelf, dock):
    return {"type": "sequence", "children": [
        {"type": "action", "name": "claim", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{shelf}"},
        {"type": "action", "name": "pick", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{dock}"},
        {"type": "action", "name": "drop", "arg": f"ex:{pkg}"}]}


# ---------- knowledge base ----------
def test_kb_loads_and_answers():
    g = load_kb()
    assert ask(g, "ASK { ex:redPackage ex:isAt ex:shelf1 }")
    assert not ask(g, "ASK { ex:redPackage ex:isAt ex:dock1 }")


# ---------- world rules ----------
def test_pick_requires_claim_and_location():
    g = load_kb()
    assert pick(g, "robotA", "redPackage") == FAILURE   # not claimed, not at shelf
    assert claim(g, "robotA", "redPackage") == SUCCESS
    assert claim(g, "robotB", "redPackage") == FAILURE  # already taken by A


# ---------- behavior trees ----------
def test_single_delivery():
    g = load_kb()
    status = run(g, {"robotA": build(deliver("redPackage", "shelf1", "dock2"))})
    assert status["robotA"] == SUCCESS
    assert ask(g, "ASK { ex:redPackage ex:isAt ex:dock2 . ex:dock2 ex:status ex:busy }")


def test_fallback_uses_second_dock_when_first_is_busy():
    g = load_kb()
    update(g, "DELETE DATA { ex:dock2 ex:status ex:free } ; INSERT DATA { ex:dock2 ex:status ex:busy }")
    tree = {"type": "sequence", "children": [
        {"type": "action", "name": "claim", "arg": "ex:redPackage"},
        {"type": "action", "name": "move_to", "arg": "ex:shelf1"},
        {"type": "action", "name": "pick", "arg": "ex:redPackage"},
        {"type": "fallback", "children": [
            {"type": "sequence", "children": [
                {"type": "condition", "ask": "ASK { ex:dock2 ex:status ex:free }"},
                {"type": "action", "name": "move_to", "arg": "ex:dock2"},
                {"type": "action", "name": "drop", "arg": "ex:redPackage"}]},
            {"type": "sequence", "children": [
                {"type": "action", "name": "move_to", "arg": "ex:dock1"},
                {"type": "action", "name": "drop", "arg": "ex:redPackage"}]}]}]}
    run(g, {"robotA": build(tree)})
    assert ask(g, "ASK { ex:redPackage ex:isAt ex:dock1 }")


def test_two_robots_conflict_resolved_by_claim():
    g = load_kb()
    b_tree = {"type": "fallback", "children": [
        deliver("redPackage", "shelf1", "dock3"),
        deliver("greenPackage", "shelf3", "dock3")]}
    run(g, {"robotA": build(deliver("redPackage", "shelf1", "dock1")), "robotB": build(b_tree)})
    assert ask(g, "ASK { ex:redPackage ex:isAt ex:dock1 . ex:greenPackage ex:isAt ex:dock3 }")