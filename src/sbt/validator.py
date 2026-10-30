# src/sbt/validator.py
"""The symbolic checker: rejects LLM-written trees before they ever run."""
import json
import re

from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery

from .kb import PREFIXES, is_a, known_terms
from .world import ACTIONS

TERM = re.compile(r"ex:(\w+)")


def validate(text: str, g: Graph) -> tuple[dict | None, list[str]]:
    """Return (tree, errors). errors == [] means the tree is safe to run."""
    try:
        tree = json.loads(text)
    except json.JSONDecodeError as e:
        return None, [f"json_error: {e}"]
    errors: list[str] = []
    _check(tree, g, known_terms(g), errors, path="root")
    return tree, errors


def _check(node, g, terms, errors, path):
    if not isinstance(node, dict) or "type" not in node:
        errors.append(f"structure_error at {path}: every node needs a 'type'")
        return
    kind = node["type"]
    if kind in ("sequence", "fallback"):
        children = node.get("children")
        if not isinstance(children, list) or not children:
            errors.append(f"structure_error at {path}: '{kind}' needs a non-empty 'children' list")
            return
        for i, child in enumerate(children):
            _check(child, g, terms, errors, f"{path}.{kind}[{i}]")
    elif kind == "condition":
        query = node.get("ask", "")
        try:
            q = prepareQuery(PREFIXES + query)
            if q.algebra.name != "AskQuery":
                errors.append(f"sparql_error at {path}: condition must be an ASK query")
        except Exception as e:
            errors.append(f"sparql_error at {path}: {str(e)[:120]}")
        for name in TERM.findall(query):
            if name not in terms:
                errors.append(f"unknown_term at {path}: ex:{name} is not in the ontology")
    elif kind == "action":
        name, arg = node.get("name"), str(node.get("arg", "")).removeprefix("ex:")
        if name not in ACTIONS:
            errors.append(f"unknown_action at {path}: '{name}' (allowed: {', '.join(ACTIONS)})")
        elif arg not in terms:
            errors.append(f"unknown_term at {path}: ex:{arg} is not in the ontology")
        elif not is_a(g, arg, ACTIONS[name][1]):
            errors.append(f"type_error at {path}: {name} needs a {ACTIONS[name][1]}, got ex:{arg}")
    else:
        errors.append(f"structure_error at {path}: unknown node type '{kind}'")