"""Idempotent minimal platform seed; no enterprise business facts."""

from .models import PublishedSnapshot
from .store import FusekiStore


def bootstrap_platform(store: FusekiStore) -> None:
    store.ensure_dataset("platform")
    if store.read_current("platform", "tree") is None:
        store.publish("platform", "tree", PublishedSnapshot(
            id="tree-v1", kind="tree", created_by="system:bootstrap",
            payload={"nodes": [
                {"id": "it", "level": 1, "parent_id": None, "label": "IT与通讯"},
                {"id": "office", "level": 2, "parent_id": "it", "label": "办公设备"},
                {"id": "computer", "level": 3, "parent_id": "office", "label": "电脑(台式机/笔记本)"},
            ], "category_keys": {"computer": "computer"}},
        ), None)
    if store.read_current("platform", "ontology") is None:
        store.publish("platform", "ontology", PublishedSnapshot(
            id="ontology-v1", kind="ontology", created_by="system:bootstrap",
            payload={"items": [], "relations": []},
        ), None)
