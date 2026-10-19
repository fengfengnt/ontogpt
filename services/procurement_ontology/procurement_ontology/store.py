"""Authenticated per-scope TDB2 persistence; no browser-provided SPARQL."""

from __future__ import annotations

import copy
import json
import re
import uuid
from pathlib import Path

import requests
from rdflib import Graph, Literal, RDF

from .models import Candidate, ChangeBatch, ExtractionRun, PublishedSnapshot, SourceRevision, utc_now
from .rdf_codec import NS, record_graph, snapshot_graph, uri
from .maintenance import WriteGate


class VersionConflict(ValueError):
    pass


class FusekiStore:
    def __init__(self, base_url: str, credentials_file: str | Path, *, dataset_prefix="procurement_", gate=None):
        self.gate = gate or WriteGate()
        if not re.fullmatch(r"[A-Za-z0-9_]+", dataset_prefix):
            raise ValueError("Invalid dataset prefix")
        self.base_url = base_url.rstrip("/")
        self.dataset_prefix = dataset_prefix
        credentials = json.loads(Path(credentials_file).read_text(encoding="utf-8"))
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.auth = (credentials["username"], credentials["password"])

    def dataset_name(self, scope_id: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,63}", scope_id):
            raise ValueError("Invalid data scope")
        return self.dataset_prefix + scope_id

    def ensure_dataset(self, scope_id: str) -> None:
        with self.gate.writer():
            self._ensure_dataset(scope_id)

    def _ensure_dataset(self, scope_id: str) -> None:
        name = self.dataset_name(scope_id)
        response = self.session.get(f"{self.base_url}/$/datasets/{name}", timeout=30)
        if response.status_code == 404:
            created = self.session.post(f"{self.base_url}/$/datasets", data={"dbName": name, "dbType": "tdb2"}, timeout=30)
            if created.status_code >= 400:
                self.session.get(f"{self.base_url}/$/datasets/{name}", timeout=30).raise_for_status()
        else:
            response.raise_for_status()

    def _query(self, scope_id: str, query: str):
        response = self.session.post(f"{self.base_url}/{self.dataset_name(scope_id)}/query", data={"query": query},
                                     headers={"Accept": "application/sparql-results+json"}, timeout=30)
        response.raise_for_status()
        return response.json()

    def _update(self, scope_id: str, update: str):
        with self.gate.writer():
            response = self.session.post(f"{self.base_url}/{self.dataset_name(scope_id)}/update", data=update.encode("utf-8"),
                                         headers={"Content-Type": "application/sparql-update"}, timeout=30)
            response.raise_for_status()
            return response

    def list_dataset_scopes(self) -> list[str]:
        response = self.session.get(self.base_url + "/$/datasets", timeout=30)
        response.raise_for_status()
        scopes = []
        for entry in response.json()["datasets"]:
            name = entry["ds.name"].lstrip("/")
            if name.startswith(self.dataset_prefix):
                scope = name[len(self.dataset_prefix):]
                self.dataset_name(scope)
                scopes.append(scope)
        return sorted(scopes)

    def _read_json(self, scope_id: str, graph, subject):
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH {graph.n3()} {{ {subject.n3()} {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        if len(rows) > 1:
            raise ValueError("Record has multiple payloads")
        return json.loads(rows[0]["payload"]["value"]) if rows else None

    def _append_immutable(self, scope_id, graph_uri, subject, value, record_type):
        previous = self._read_json(scope_id, graph_uri, subject)
        if previous is not None:
            if previous != value:
                raise ValueError("Immutable record already exists with different content")
            return
        graph = record_graph(subject, value, record_type)
        if record_type == "SourceRevision":
            graph.add((subject, NS.text, Literal(value["text"])))
            graph.add((subject, NS.sha256, Literal(value["sha256"])))
            graph.add((subject, NS.simulated, Literal(value["simulated"])))
        self._update(scope_id, f"""
            INSERT {{ GRAPH {graph_uri.n3()} {{ {graph.serialize(format='nt')} }} }}
            WHERE {{ FILTER NOT EXISTS {{ GRAPH {graph_uri.n3()} {{ {subject.n3()} {NS.payload.n3()} ?old }} }} }}
        """)
        if self._read_json(scope_id, graph_uri, subject) != value:
            raise ValueError("Concurrent immutable record conflict")

    def append_source(self, scope_id: str, source: SourceRevision) -> None:
        if source.scope_id != scope_id:
            raise ValueError("Source does not belong to data scope")
        self._append_immutable(scope_id, uri(scope_id, "source-graph", source.id), uri(scope_id, "source", source.id),
                               source.model_dump(mode="json"), "SourceRevision")

    def read_source(self, scope_id: str, source_id: str) -> SourceRevision | None:
        value = self._read_json(scope_id, uri(scope_id, "source-graph", source_id), uri(scope_id, "source", source_id))
        return SourceRevision.model_validate(value) if value is not None else None

    def list_sources(self, scope_id: str) -> list[SourceRevision]:
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH ?graph {{ ?source a {NS.SourceRevision.n3()}; {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        return [SourceRevision.model_validate_json(row["payload"]["value"]) for row in rows]

    def append_candidates(self, scope_id: str, batch_id: str, candidates: list[Candidate]) -> None:
        for candidate in candidates:
            self._append_immutable(scope_id, uri(scope_id, "batch", batch_id), uri(scope_id, "candidate", candidate.id),
                                   candidate.model_dump(mode="json"), "Candidate")

    def read_batch(self, scope_id: str, batch_id: str) -> list[Candidate]:
        graph = uri(scope_id, "batch", batch_id)
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH {graph.n3()} {{ ?candidate a {NS.Candidate.n3()}; {NS.payload.n3()} ?payload }} }} ORDER BY ?candidate")["results"]["bindings"]
        return [Candidate.model_validate_json(row["payload"]["value"]) for row in rows]

    def save_run(self, scope_id: str, run: ExtractionRun) -> None:
        if run.scope_id != scope_id:
            raise ValueError("Run does not belong to data scope")
        graph_uri = uri(scope_id, "run", run.id)
        event = uri(scope_id, "run-event", uuid.uuid4().hex)
        graph = record_graph(event, run.model_dump(mode="json"), "RunEvent")
        self._update(scope_id, f"""
            DELETE {{ GRAPH {graph_uri.n3()} {{ {graph_uri.n3()} {NS.latest_event.n3()} ?old }} }}
            INSERT {{ GRAPH {graph_uri.n3()} {{
              {graph.serialize(format='nt')}
              {graph_uri.n3()} a {NS.ExtractionRun.n3()}; {NS.latest_event.n3()} {event.n3()}.
            }} }}
            WHERE {{ OPTIONAL {{ GRAPH {graph_uri.n3()} {{ {graph_uri.n3()} {NS.latest_event.n3()} ?old }} }} }}
        """)

    def read_run(self, scope_id: str, run_id: str) -> ExtractionRun | None:
        graph = uri(scope_id, "run", run_id)
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH {graph.n3()} {{ {graph.n3()} {NS.latest_event.n3()} ?event. ?event {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        if len(rows) > 1:
            raise ValueError("Run has multiple current events")
        return ExtractionRun.model_validate_json(rows[0]["payload"]["value"]) if rows else None

    def list_runs(self, scope_id: str) -> list[ExtractionRun]:
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH ?graph {{ ?graph a {NS.ExtractionRun.n3()}; {NS.latest_event.n3()} ?event. ?event {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        return [ExtractionRun.model_validate_json(row["payload"]["value"]) for row in rows]

    def save_change_batch(self, scope_id: str, batch: ChangeBatch) -> None:
        if batch.scope_id != scope_id:
            raise ValueError("Batch does not belong to scope")
        graph_uri = uri(scope_id, "changes", batch.id)
        event = uri(scope_id, "change-event", uuid.uuid4().hex)
        graph = record_graph(event, batch.model_dump(mode="json"), "ChangeEvent")
        self._update(scope_id, f"""
          DELETE {{ GRAPH {graph_uri.n3()} {{ {graph_uri.n3()} {NS.latest_event.n3()} ?old }} }}
          INSERT {{ GRAPH {graph_uri.n3()} {{ {graph.serialize(format='nt')}
            {graph_uri.n3()} a {NS.ChangeBatch.n3()}; {NS.latest_event.n3()} {event.n3()}. }} }}
          WHERE {{ OPTIONAL {{ GRAPH {graph_uri.n3()} {{ {graph_uri.n3()} {NS.latest_event.n3()} ?old }} }} }}
        """)

    def read_change_batch(self, scope_id: str, batch_id: str) -> ChangeBatch | None:
        graph = uri(scope_id, "changes", batch_id)
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH {graph.n3()} {{ {graph.n3()} {NS.latest_event.n3()} ?event. ?event {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        if len(rows) > 1:
            raise ValueError("Batch has multiple current events")
        return ChangeBatch.model_validate_json(rows[0]["payload"]["value"]) if rows else None

    def list_change_batches(self, scope_id: str) -> list[ChangeBatch]:
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH ?graph {{ ?graph a {NS.ChangeBatch.n3()}; {NS.latest_event.n3()} ?event. ?event {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        return [ChangeBatch.model_validate_json(row["payload"]["value"]) for row in rows]

    def append_schema_draft(self, scope_id: str, record: dict) -> None:
        if record["gap"]["company_id"] != scope_id:
            raise ValueError("Schema draft does not belong to scope")
        subject = uri(scope_id, "schema-draft", record["id"])
        self._append_immutable(scope_id, subject, subject, record, "SchemaDraft")

    def read_schema_draft(self, scope_id: str, draft_id: str) -> dict | None:
        subject = uri(scope_id, "schema-draft", draft_id)
        return self._read_json(scope_id, subject, subject)

    def list_schema_drafts(self, scope_id: str) -> list[dict]:
        rows = self._query(scope_id, f"SELECT ?payload WHERE {{ GRAPH ?graph {{ ?graph a {NS.SchemaDraft.n3()}; {NS.payload.n3()} ?payload }} }}")["results"]["bindings"]
        return [json.loads(row["payload"]["value"]) for row in rows]

    @staticmethod
    def _current_predicate(kind: str):
        if kind not in {"tree", "ontology"}:
            raise ValueError("Invalid snapshot kind")
        return NS["current_" + kind]

    def read_current(self, scope_id: str, kind: str) -> PublishedSnapshot | None:
        predicate = self._current_predicate(kind)
        control, root = uri(scope_id, "control", "current"), uri(scope_id, "root", "knowledge")
        rows = self._query(scope_id, f"""
            SELECT ?payload WHERE {{ GRAPH {control.n3()} {{ {root.n3()} {predicate.n3()} ?version }}
              GRAPH ?version {{ ?version {NS.payload.n3()} ?payload }} }}
        """)["results"]["bindings"]
        if len(rows) > 1:
            raise ValueError("Multiple current versions")
        return PublishedSnapshot.model_validate_json(rows[0]["payload"]["value"]) if rows else None

    def read_version(self, scope_id: str, kind: str, version_id: str) -> PublishedSnapshot | None:
        self._current_predicate(kind)
        graph = uri(scope_id, kind, version_id)
        value = self._read_json(scope_id, graph, graph)
        return PublishedSnapshot.model_validate(value) if value is not None else None

    def read_pair(self, scope_id: str) -> dict[str, PublishedSnapshot]:
        control, root = uri(scope_id, "control", "current"), uri(scope_id, "root", "knowledge")
        rows = self._query(scope_id, f"""SELECT ?tree ?ontology WHERE {{
          GRAPH {control.n3()} {{ {root.n3()} {NS.current_tree.n3()} ?t; {NS.current_ontology.n3()} ?o. }}
          GRAPH ?t {{ ?t {NS.payload.n3()} ?tree }} GRAPH ?o {{ ?o {NS.payload.n3()} ?ontology }}
        }}""")["results"]["bindings"]
        if len(rows) != 1:
            raise ValueError("Current tree/ontology pair is unavailable")
        return {kind: PublishedSnapshot.model_validate_json(rows[0][kind]["value"]) for kind in ("tree", "ontology")}

    def publish(self, scope_id: str, kind: str, snapshot: PublishedSnapshot, expected_version: str | None,
                *, expected_versions: dict[str, str] | None = None) -> None:
        predicate = self._current_predicate(kind)
        if snapshot.kind != kind or snapshot.previous_id != expected_version:
            raise ValueError("Snapshot kind/previous version does not match publication")
        existing = self.read_version(scope_id, kind, snapshot.id)
        if existing:
            if existing != snapshot:
                raise ValueError("Cannot overwrite a published version")
            return
        version = uri(scope_id, kind, snapshot.id)
        control, root = uri(scope_id, "control", "current"), uri(scope_id, "root", "knowledge")
        old_pattern = f"GRAPH {control.n3()} {{ {root.n3()} {predicate.n3()} {uri(scope_id, kind, expected_version).n3()} }}" if expected_version else ""
        delete = f"DELETE {{ {old_pattern} }}" if expected_version else ""
        where = old_pattern if expected_version else f"FILTER NOT EXISTS {{ GRAPH {control.n3()} {{ {root.n3()} {predicate.n3()} ?old }} }}"
        if expected_versions:
            where += " ".join(f" GRAPH {control.n3()} {{ {root.n3()} {self._current_predicate(other).n3()} {uri(scope_id, other, identifier).n3()} }}" for other, identifier in expected_versions.items())
        self._update(scope_id, f"""
            {delete}
            INSERT {{ GRAPH {control.n3()} {{ {root.n3()} {predicate.n3()} {version.n3()} }}
                     GRAPH {version.n3()} {{ {snapshot_graph(scope_id, snapshot).serialize(format='nt')} }} }}
            WHERE {{ {where} FILTER NOT EXISTS {{ GRAPH {version.n3()} {{ ?s ?p ?o }} }} }}
        """)
        if self.read_version(scope_id, kind, snapshot.id) != snapshot:
            raise VersionConflict("Current version changed before publication")

    def _initialization(self, scope_id: str) -> dict:
        control, root = uri(scope_id, "control", "current"), uri(scope_id, "root", "knowledge")
        rows = self._query(scope_id, f"SELECT ?p ?v WHERE {{ GRAPH {control.n3()} {{ {root.n3()} ?p ?v }} }}")["results"]["bindings"]
        return {row["p"]["value"]: row["v"]["value"] for row in rows}

    def provision_company(self, company_id: str, platform_versions: dict[str, str]) -> None:
        if company_id == "platform":
            raise ValueError("Cannot provision platform as a company")
        self.ensure_dataset(company_id)
        control, root = uri(company_id, "control", "current"), uri(company_id, "root", "knowledge")
        state = self._initialization(company_id)
        if state.get(str(NS.provisioned)) == "true":
            return
        if str(NS.initial_tree) not in state:
            graph = Graph()
            graph.add((root, NS.initial_tree, Literal(platform_versions["tree"])))
            graph.add((root, NS.initial_ontology, Literal(platform_versions["ontology"])))
            graph.add((root, NS.initialized_at, Literal(utc_now().isoformat())))
            self._update(company_id, f"INSERT {{ GRAPH {control.n3()} {{ {graph.serialize(format='nt')} }} }} WHERE {{ FILTER NOT EXISTS {{ GRAPH {control.n3()} {{ {root.n3()} {NS.initial_tree.n3()} ?old }} }} }}")
            state = self._initialization(company_id)
        platform_versions = {kind: state[str(NS["initial_" + kind])] for kind in ("tree", "ontology")}
        tree = self.read_version("platform", "tree", platform_versions["tree"])
        ontology = self.read_version("platform", "ontology", platform_versions["ontology"])
        if tree is None or ontology is None:
            raise ValueError("Platform template version is unavailable")
        tree_payload, ontology_payload = copy.deepcopy(tree.payload), copy.deepcopy(ontology.payload)
        category_map = {node["id"]: company_id + ":" + node["id"] for node in tree_payload["nodes"]}
        for node in tree_payload["nodes"]:
            node["id"] = category_map[node["id"]]
            if node.get("parent_id"):
                node["parent_id"] = category_map[node["parent_id"]]
        tree_payload["category_keys"] = {key: category_map[value] for key, value in tree_payload.get("category_keys", {}).items()}
        items, relations = ontology_payload.get("items", []), ontology_payload.get("relations", [])
        item_map = {item["id"]: company_id + ":" + item["id"] for item in items}
        for item in items:
            item["id"], item["category_id"] = item_map[item["id"]], category_map[item["category_id"]]
        for relation in relations:
            relation["id"] = company_id + ":" + relation["id"]
            relation["subject_id"], relation["object_id"] = item_map[relation["subject_id"]], item_map[relation["object_id"]]
        for record in items + relations:
            for span in record.get("source_spans", []):
                original = self.read_source("platform", span["revision_id"])
                if original is None:
                    raise ValueError("Platform source closure is incomplete")
                copied = original.model_copy(update={"id": company_id + ":" + original.id, "scope_id": company_id})
                self.append_source(company_id, copied)
                span["revision_id"] = copied.id
        for kind, original, payload in (("tree", tree, tree_payload), ("ontology", ontology, ontology_payload)):
            snapshot = PublishedSnapshot(id="initial-" + original.id, kind=kind, payload=payload,
                                         created_by="system:provision", created_at=state[str(NS.initialized_at)])
            self.publish(company_id, kind, snapshot, None)
        self._update(company_id, f"INSERT DATA {{ GRAPH {control.n3()} {{ {root.n3()} {NS.provisioned.n3()} true }} }}")
