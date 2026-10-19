"""One read boundary shared by Web, MCP and Agent."""

import json

from .identity import authorize
from .store import VersionConflict


def version_pair(pair):
    return {kind: snapshot.id for kind, snapshot in pair.items()}


def category_path(nodes, category_id):
    by_id, path = {node["id"]: node for node in nodes}, []
    while category_id:
        node = by_id[category_id]
        path.insert(0, node)
        category_id = node.get("parent_id")
    return path


class KnowledgeQuery:
    def __init__(self, store):
        self.store = store

    def _pair(self, identity, observed=None):
        authorize(identity, identity.scope_id, "read")
        pair = self.store.read_pair(identity.scope_id)
        if observed is not None and observed != version_pair(pair):
            raise VersionConflict("VERSION_CHANGED")
        return pair

    def versions(self, identity):
        return version_pair(self._pair(identity))

    def tree(self, identity):
        pair = self._pair(identity)
        return {**pair["tree"].payload, "versions": version_pair(pair)}

    def search(self, identity, text, category_key):
        pair = self._pair(identity)
        category = pair["tree"].payload.get("category_keys", {}).get(category_key)
        query = text.strip().casefold()
        items = [item for item in pair["ontology"].payload.get("items", [])
                 if item["category_id"] == category and query in json.dumps(item, ensure_ascii=False).casefold()]
        return {"items": items, "count": len(items), "versions": version_pair(pair)}

    def get(self, identity, item_id, observed_version=None):
        pair = self._pair(identity, observed_version)
        items = {item["id"]: item for item in pair["ontology"].payload.get("items", [])}
        if item_id not in items:
            raise KeyError("条目不存在")
        item = items[item_id]
        relations = [relation for relation in pair["ontology"].payload.get("relations", [])
                     if item_id in (relation["subject_id"], relation["object_id"])
                     and relation["subject_id"] in items and relation["object_id"] in items]
        sources = []
        for record in [item, *relations]:
            for span in record.get("source_spans", []):
                source = self.store.read_source(identity.scope_id, span["revision_id"])
                if source is None:
                    raise ValueError("来源闭包不完整")
                sources.append({**span, "simulated": source.simulated, "source_sha256": source.sha256})
        return {"item": item, "relations": relations, "sources": sources,
                "category_path": category_path(pair["tree"].payload["nodes"], item["category_id"]),
                "versions": version_pair(pair)}
