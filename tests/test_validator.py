# tests/test_validator.py
import json

from sbt.kb import load_kb
from sbt.validator import validate


def deliver(pkg, shelf, dock):
    return {"type": "sequence", "children": [
        {"type": "action", "name": "claim", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{shelf}"},
        {"type": "action", "name": "pick", "arg": f"ex:{pkg}"},
        {"type": "action", "name": "move_to", "arg": f"ex:{dock}"},
        {"type": "action", "name": "drop", "arg": f"ex:{pkg}"}]}


def test_validator_accepts_good_tree():
    _, errors = validate(json.dumps(deliver("redPackage", "shelf1", "dock1")), load_kb())
    assert errors == []


def test_validator_catches_mistakes():
    g = load_kb()
    bad = {"type": "sequence", "children": [
        {"type": "condition", "ask": "ASK { ex:redPackage ex:isAt ex:dock7 }"},  # invented dock
        {"type": "action", "name": "fly", "arg": "ex:shelf1"},                    # invented action
        {"type": "action", "name": "pick", "arg": "ex:dock1"},                    # wrong type
        {"type": "condition", "ask": "ASK { ex:redPackage ex:isAt "}]}            # broken SPARQL
    _, errors = validate(json.dumps(bad), g)
    kinds = {e.split(" ")[0] for e in errors}
    assert {"unknown_term", "unknown_action", "type_error", "sparql_error"} <= kinds
    _, errors = validate("not json", g)
    assert errors[0].startswith("json_error")