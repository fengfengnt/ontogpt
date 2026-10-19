"""RDF terms and projections generated from one validated version payload."""

import json
from urllib.parse import quote

from rdflib import BNode, Graph, Literal, Namespace, RDF, RDFS, URIRef

from .models import PublishedSnapshot

NS = Namespace("urn:procurement:vocab:")
JSON_TYPE = URIRef(str(RDF) + "JSON")


def uri(scope_id: str, kind: str, identifier: str) -> URIRef:
    return URIRef(f"urn:procurement:{scope_id}:{kind}:{quote(str(identifier), safe='')}")


def json_literal(value) -> Literal:
    return Literal(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False), datatype=JSON_TYPE)


def record_graph(subject: URIRef, value, record_type: str) -> Graph:
    graph = Graph()
    graph.add((subject, RDF.type, NS[record_type]))
    graph.add((subject, NS.payload, json_literal(value)))
    return graph


def snapshot_graph(scope_id: str, snapshot: PublishedSnapshot) -> Graph:
    subject = uri(scope_id, snapshot.kind, snapshot.id)
    graph = record_graph(subject, snapshot.model_dump(mode="json"), "PublishedSnapshot")
    graph.add((subject, NS.created_by, Literal(snapshot.created_by)))
    graph.add((subject, NS.created_at, Literal(snapshot.created_at)))
    if snapshot.previous_id:
        graph.add((subject, NS.previous_version, uri(scope_id, snapshot.kind, snapshot.previous_id)))
    for node in snapshot.payload.get("nodes", []):
        node_uri = uri(scope_id, "category", node["id"])
        graph.add((node_uri, RDF.type, NS.CategoryNode))
        graph.add((node_uri, RDFS.label, Literal(node["label"])))
        graph.add((node_uri, NS.level, Literal(node["level"])))
        if node.get("parent_id"):
            graph.add((node_uri, NS.parent, uri(scope_id, "category", node["parent_id"])))
    for item in snapshot.payload.get("items", []):
        item_uri = uri(scope_id, "item", item["id"])
        graph.add((item_uri, RDF.type, uri(scope_id, "type", item["kind"])))
        graph.add((item_uri, RDFS.label, Literal(item["label"])))
        graph.add((item_uri, RDFS.comment, Literal(item.get("description", ""))))
        graph.add((item_uri, NS.category, uri(scope_id, "category", item["category_id"])))
        graph.add((item_uri, NS.applicability, json_literal(item.get("scope", {}))))
        graph.add((item_uri, NS.simulated, Literal(item.get("simulated", False))))
        for key, value in item.get("properties", {}).items():
            graph.add((item_uri, uri(scope_id, "property", key), json_literal(value)))
        _evidence(graph, scope_id, item_uri, item.get("source_spans", []))
    for relation in snapshot.payload.get("relations", []):
        relation_uri = uri(scope_id, "relation-record", relation["id"])
        subject_uri = uri(scope_id, "item", relation["subject_id"])
        predicate_uri = uri(scope_id, "relation", relation["predicate"])
        object_uri = uri(scope_id, "item", relation["object_id"])
        graph.add((subject_uri, predicate_uri, object_uri))
        graph.add((relation_uri, RDF.type, RDF.Statement))
        graph.add((relation_uri, RDF.subject, subject_uri))
        graph.add((relation_uri, RDF.predicate, predicate_uri))
        graph.add((relation_uri, RDF.object, object_uri))
        graph.add((relation_uri, NS.applicability, json_literal(relation.get("scope", {}))))
        _evidence(graph, scope_id, relation_uri, relation.get("source_spans", []))
    return graph


def _evidence(graph: Graph, scope_id: str, subject: URIRef, spans: list[dict]) -> None:
    for span in spans:
        node = BNode()
        graph.add((subject, NS.evidence, node))
        graph.add((node, NS.source, uri(scope_id, "source", span["revision_id"])))
        graph.add((node, NS.quote, Literal(span["quote"])))
        graph.add((node, NS.start, Literal(span["start"])))
        graph.add((node, NS.end, Literal(span["end"])))
