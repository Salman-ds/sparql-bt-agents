# src/sbt/kb.py
"""The knowledge base: one RDF graph that holds the whole world state."""
from pathlib import Path

from rdflib import Graph, Namespace, URIRef

EX = Namespace("http://example.org/warehouse#")
PREFIXES = (
    "PREFIX ex: <http://example.org/warehouse#>\n"
    "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
)
DATA = Path(__file__).resolve().parents[2] / "data" / "warehouse.ttl"


def load_kb(path: Path = DATA) -> Graph:
    g = Graph()
    g.parse(path, format="turtle")
    return g


def ask(g: Graph, query: str) -> bool:
    """Run a SPARQL ASK query (prefixes added automatically)."""
    return bool(g.query(PREFIXES + query).askAnswer)


def update(g: Graph, query: str) -> None:
    """Run a SPARQL UPDATE (prefixes added automatically)."""
    g.update(PREFIXES + query)


def known_terms(g: Graph) -> set[str]:
    """Every ex: name that exists in the graph, e.g. {'robotA', 'isAt', ...}."""
    names = set()
    for triple in g:
        for term in triple:
            if isinstance(term, URIRef) and str(term).startswith(str(EX)):
                names.add(str(term)[len(str(EX)):])
    return names


def is_a(g: Graph, name: str, cls: str) -> bool:
    """Is ex:name an instance of ex:cls (including subclasses)?"""
    return ask(g, f"ASK {{ ex:{name} rdf:type/rdfs:subClassOf* ex:{cls} }}")

def state_facts(g: Graph) -> list[str]:
    """The current world state as short 'ex:subject ex:predicate ex:object' lines."""
    rows = g.query(PREFIXES + """
        SELECT ?s ?p ?o WHERE {
            VALUES ?p { ex:isAt ex:heldBy ex:claimedBy ex:status }
            ?s ?p ?o .
        } ORDER BY ?s ?p""")
    short = lambda term: "ex:" + str(term)[len(str(EX)):]
    return [f"{short(s)} {short(p)} {short(o)}" for s, p, o in rows]