# src/sbt/planner.py
"""LLM planner: English instruction -> behavior tree (JSON), with optional repair loop."""
import json

import requests
from rdflib import Graph

from .kb import state_facts
from .validator import validate

OLLAMA_URL = "http://localhost:11434/api/chat"

SYSTEM_PROMPT = """You write behavior trees for a warehouse robot. Reply with ONE JSON object only.

Node types:
  {"type": "sequence", "children": [...]}   run children in order, stop at the first failure
  {"type": "fallback", "children": [...]}   try children in order, stop at the first success
  {"type": "condition", "ask": "ASK { ... }"}  a SPARQL ASK query using the ex: prefix
  {"type": "action", "name": NAME, "arg": "ex:..."}

Actions (the robot running the tree is the one acting):
  move_to <Place>     walk to a shelf or dock
  claim   <Package>   reserve a package (fails if another robot has it); required before pick
  pick    <Package>   pick up a package at the robot's current place
  drop    <Package>   put the held package down at the current place (a dock must be free)

Known terms (use ONLY these):
  Robots: ex:robotA, ex:robotB
  Packages: ex:redPackage, ex:bluePackage, ex:greenPackage
  Shelves: ex:shelf1, ex:shelf2, ex:shelf3     Docks: ex:dock1, ex:dock2, ex:dock3
  Properties: ex:isAt (package/robot -> place), ex:heldBy, ex:claimedBy, ex:status (dock -> ex:free or ex:busy)

Example. Instruction: "Take the green package to dock 1."
{"type": "sequence", "children": [
  {"type": "condition", "ask": "ASK { ex:greenPackage ex:isAt ex:shelf3 }"},
  {"type": "action", "name": "claim", "arg": "ex:greenPackage"},
  {"type": "action", "name": "move_to", "arg": "ex:shelf3"},
  {"type": "action", "name": "pick", "arg": "ex:greenPackage"},
  {"type": "action", "name": "move_to", "arg": "ex:dock1"},
  {"type": "action", "name": "drop", "arg": "ex:greenPackage"}]}

Example. Instruction: "Bring the blue package to dock 2, or to dock 3 if dock 2 is busy."
{"type": "sequence", "children": [
  {"type": "action", "name": "claim", "arg": "ex:bluePackage"},
  {"type": "action", "name": "move_to", "arg": "ex:shelf2"},
  {"type": "action", "name": "pick", "arg": "ex:bluePackage"},
  {"type": "fallback", "children": [
    {"type": "sequence", "children": [
      {"type": "condition", "ask": "ASK { ex:dock2 ex:status ex:free }"},
      {"type": "action", "name": "move_to", "arg": "ex:dock2"},
      {"type": "action", "name": "drop", "arg": "ex:bluePackage"}]},
    {"type": "sequence", "children": [
      {"type": "action", "name": "move_to", "arg": "ex:dock3"},
      {"type": "action", "name": "drop", "arg": "ex:bluePackage"}]}]}]}
"""


def ask_llm(messages: list[dict], model: str) -> str:
    resp = requests.post(OLLAMA_URL, json={
        "model": model, "messages": messages, "stream": False,
        "format": "json", "options": {"temperature": 0},
    }, timeout=600)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def plan(instruction: str, g: Graph, model: str, max_repairs: int = 0,
         grounded: bool = False) -> dict:
    """Generate a tree. With max_repairs > 0, feed validator errors back to the LLM.
    With grounded=True, the prompt also lists the current world state from the graph."""
    prompt = f"Instruction: {instruction}"
    if grounded:
        prompt = "Current world state:\n" + "\n".join(state_facts(g)) + "\n\n" + prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}]
    history = []
    for attempt in range(max_repairs + 1):
        text = ask_llm(messages, model)
        tree, errors = validate(text, g)
        history.append({"output": text, "errors": errors})
        if not errors or attempt == max_repairs:
            break
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "Your tree has errors:\n- " + "\n- ".join(errors)
                      + "\nReturn the corrected JSON tree only."}]
    return {"tree": tree, "errors": errors, "repairs": len(history) - 1, "history": history}


if __name__ == "__main__":
    from .kb import load_kb
    result = plan("Take the red package to dock 2.", load_kb(), "qwen2.5:3b", max_repairs=2)
    print(json.dumps(result["tree"], indent=2), "\nerrors:", result["errors"])