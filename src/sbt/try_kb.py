from sbt.kb import load_kb, ask, update, known_terms, is_a

g = load_kb()
print("facts:", len(g))
print("red on shelf1?", ask(g, "ASK { ex:redPackage ex:isAt ex:shelf1 }"))
print("dock2 is a Place?", is_a(g, "dock2", "Place"))
update(g, "DELETE DATA { ex:dock2 ex:status ex:free } ; INSERT DATA { ex:dock2 ex:status ex:busy }")
print("dock2 busy now?", ask(g, "ASK { ex:dock2 ex:status ex:busy }"))
print("dock7 known?", "dock7" in known_terms(g))