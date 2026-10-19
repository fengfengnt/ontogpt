"""Human review, validated changes and immutable publication in the actor's scope."""

import copy
import threading
import uuid

from .identity import authorize
from .maintenance import business_write
from .models import CategoryNode, ChangeBatch, KnowledgeItem, KnowledgeRelation, PublishedSnapshot, utc_now
from .query import version_pair
from .store import VersionConflict


class GovernanceService:
    def __init__(self, store, catalog):
        self.store, self.catalog = store, catalog
        self._lock = threading.RLock()

    def _pair(self, identity, observed=None):
        pair = self.store.read_pair(identity.scope_id)
        if observed is not None and version_pair(pair) != observed:
            raise VersionConflict("STALE_BASE_VERSION")
        return pair

    @staticmethod
    def _audit(batch, identity, action, **details):
        batch.audit.append({"actor_id": identity.account_id, "at": utc_now().isoformat(), "action": action, **details})

    def _batch(self, identity, kind, pair, batch_id=None):
        batch = self.store.read_change_batch(identity.scope_id, batch_id) if batch_id else None
        if batch:
            if batch.kind != kind or batch.status != "PENDING":
                raise ValueError("批次不可修改")
            if batch.base_versions != version_pair(pair):
                raise VersionConflict("STALE_BASE_VERSION")
            return batch
        if batch_id:
            raise KeyError("批次不存在")
        return ChangeBatch(id="change-" + uuid.uuid4().hex, scope_id=identity.scope_id, kind=kind,
                           base_versions=version_pair(pair), created_by=identity.account_id)

    @business_write
    def review(self, identity, candidate_id, decision, *, corrected=None):
        authorize(identity, identity.scope_id, "review")
        if decision not in {"ACCEPTED", "REJECTED"}:
            raise ValueError("审核决定无效")
        with self._lock:
            run = next((run for run in self.store.list_runs(identity.scope_id)
                        if run.status == "SUCCEEDED" and candidate_id in run.candidate_ids), None)
            if not run:
                raise ValueError("成功运行中的候选不存在")
            candidate = next(candidate for candidate in self.store.read_batch(identity.scope_id, run.batch_id) if candidate.id == candidate_id)
            pair = self._pair(identity)
            batch = self.store.read_change_batch(identity.scope_id, run.batch_id)
            if batch is None:
                batch = ChangeBatch(id=run.batch_id, kind="ontology", scope_id=identity.scope_id,
                                    base_versions=version_pair(pair), candidate_ids=run.candidate_ids, created_by=identity.account_id)
            else:
                batch = self._batch(identity, "ontology", pair, batch.id)
            item = type(candidate.item).model_validate(corrected) if corrected is not None else candidate.item
            if decision == "ACCEPTED":
                self._evidence(identity.scope_id, item)
                if getattr(item, "object_id", "").startswith("unresolved:") or getattr(item, "subject_id", "").startswith("unresolved:"):
                    raise ValueError("关系端点未解析")
            batch.decisions[candidate_id] = {"decision": decision, "item": item.model_dump(mode="json")}
            self._audit(batch, identity, "review", candidate_id=candidate_id, decision=decision)
            self.store.save_change_batch(identity.scope_id, batch)
            return batch

    @business_write
    def restart_review(self, identity, batch_id, observed_version):
        authorize(identity, identity.scope_id, "review")
        with self._lock:
            pair = self._pair(identity, observed_version)
            batch = self.store.read_change_batch(identity.scope_id, batch_id)
            if batch is None:
                raise KeyError("批次不存在")
            if batch.status != "PENDING" or batch.kind != "ontology" or not batch.candidate_ids or batch.changes:
                raise ValueError("只能重新审核未发布的候选批次")
            self._audit(batch, identity, "restart_review", previous_versions=batch.base_versions,
                        discarded_decisions=len(batch.decisions))
            batch.base_versions = version_pair(pair)
            batch.decisions = {}
            self.store.save_change_batch(identity.scope_id, batch)
            return batch

    @business_write
    def edit_item(self, identity, change, observed_version):
        return self._edit(identity, "ontology", change, observed_version)

    @business_write
    def edit_tree(self, identity, change, observed_version):
        return self._edit(identity, "tree", change, observed_version)

    def _edit(self, identity, kind, change, observed):
        authorize(identity, identity.scope_id, "write")
        if change.get("scope_id", identity.scope_id) != identity.scope_id:
            raise PermissionError("不能修改其他数据域")
        allowed = {"add_node", "update_node", "remove_node"} if kind == "tree" else {
            "add_item", "update_item", "remove_item", "add_relation", "update_relation", "remove_relation"}
        if change.get("op") not in allowed:
            raise ValueError("操作类型无效")
        with self._lock:
            pair = self._pair(identity, observed)
            batch = self._batch(identity, kind, pair, change.get("batch_id"))
            batch.changes.append({key: value for key, value in change.items() if key not in {"batch_id", "scope_id"}})
            payload = self._apply(batch, pair)
            self._validate(identity.scope_id, kind, payload, pair)
            self._audit(batch, identity, "edit", change=batch.changes[-1])
            self.store.save_change_batch(identity.scope_id, batch)
            return batch

    def _apply(self, batch, pair):
        payload = copy.deepcopy(pair[batch.kind].payload)
        changes = list(batch.changes)
        for review in batch.decisions.values():
            if review["decision"] == "ACCEPTED":
                item = review["item"]
                field = "relation" if "subject_id" in item else "item"
                changes.append({"op": "add_" + field, field: item})
        for change in changes:
            action, target = change["op"].split("_", 1)
            key = {"node": "nodes", "item": "items", "relation": "relations"}[target]
            records = payload.setdefault(key, [])
            identifier = change["id"] if action == "remove" else change[target]["id"]
            index = next((index for index, value in enumerate(records) if value["id"] == identifier), None)
            if action == "add":
                if index is not None:
                    raise ValueError("ID 已存在；修改必须显式使用 update")
                records.append(copy.deepcopy(change[target]))
            elif index is None:
                raise ValueError("待修改记录不存在")
            elif action == "remove":
                records.pop(index)
                if target == "node":
                    payload["category_keys"] = {k: v for k, v in payload.get("category_keys", {}).items() if v != identifier}
            else:
                records[index] = copy.deepcopy(change[target])
            if target == "node" and change.get("category_key"):
                category_key = change["category_key"]
                keys = payload.setdefault("category_keys", {})
                if not isinstance(category_key, str) or (category_key in keys and keys[category_key] != identifier):
                    raise ValueError("二级品类键已绑定其他节点，不能重绑定")
                keys[category_key] = identifier
        return payload

    def _evidence(self, scope_id, record):
        if not record.source_spans:
            raise ValueError("发布事实需要原文证据")
        simulated = False
        for span in record.source_spans:
            source = self.store.read_source(scope_id, span.revision_id)
            if source is None:
                raise ValueError("原文来源不在当前数据域")
            span.validate_against(source)
            simulated |= source.simulated
        if isinstance(record, KnowledgeItem) and simulated and not record.simulated:
            raise ValueError("模拟来源不得变成真实事实")
        if record.scope.valid_from and record.scope.valid_to and record.scope.valid_from > record.scope.valid_to:
            raise ValueError("有效期范围无效")

    def _validate(self, scope_id, kind, payload, pair):
        tree = payload if kind == "tree" else pair["tree"].payload
        nodes = [CategoryNode.model_validate(node) for node in tree["nodes"]]
        by_id = {node.id: node for node in nodes}
        if len(by_id) != len(nodes):
            raise ValueError("分类节点 ID 重复")
        for node in nodes:
            if node.parent_id and (node.parent_id not in by_id or by_id[node.parent_id].level != node.level - 1):
                raise ValueError("分类父级不存在或层级无效")
        for identifier in tree.get("category_keys", {}).values():
            if identifier not in by_id or by_id[identifier].level != 3:
                raise ValueError("二级品类键必须对应第三级节点")
        ontology = payload if kind == "ontology" else pair["ontology"].payload
        items = [KnowledgeItem.model_validate(item) for item in ontology.get("items", [])]
        item_map = {item.id: item for item in items}
        previous_items = {item["id"]: item for item in pair["ontology"].payload.get("items", [])}
        if len(item_map) != len(items):
            raise ValueError("条目 ID 重复")
        for item in items:
            if item.category_id not in by_id or by_id[item.category_id].level != 3:
                raise ValueError("分类被本体引用，不能删除或改变层级")
            if kind == "ontology":
                self._evidence(scope_id, item)
                if item.access_policy_ref is not None:
                    raise ValueError("MVP 的 access_policy_ref 须为空")
                if scope_id != "platform" and item.model_dump(mode="json") != previous_items.get(item.id):
                    category_key = next((key for key, identifier in tree.get("category_keys", {}).items() if identifier == item.category_id), None)
                    binding = self.catalog.active(scope_id, category_key)
                    ranges = {slot.range for slot in binding.schema_view.class_induced_slots(binding.root_class)
                              if slot.name not in {"relations", "unmapped_suggestions"}}
                    if item.kind not in ranges:
                        raise ValueError("条目类型不符合当前启用 schema")
                    getattr(binding.module, item.kind).model_validate({**item.properties, "label": item.label,
                        "statement": item.description, "project_ref": item.scope.project_ref,
                        "device_type": item.scope.device_type, "stage": item.scope.stage})
                if item.kind in {"InternalCost", "PricingStrategy"} and not item.scope.project_ref:
                    raise ValueError("内部成本和报价策略须保留项目范围")
                if item.kind == "ConditionTemplate" and item.properties.get("case_threshold") and not item.scope.project_ref:
                    raise ValueError("案例门槛须保留项目范围")
        relations = [KnowledgeRelation.model_validate(value) for value in ontology.get("relations", [])]
        if len({relation.id for relation in relations}) != len(relations):
            raise ValueError("关系 ID 重复")
        for relation in relations:
            if relation.subject_id not in item_map or relation.object_id not in item_map:
                raise ValueError("关系引用不在当前本体")
            if kind == "ontology":
                self._evidence(scope_id, relation)
                if scope_id == "platform":
                    if relation.predicate != "related_to":
                        raise ValueError("通用关系类型无效")
                else:
                    subject, object_ = item_map[relation.subject_id], item_map[relation.object_id]
                    if subject.category_id != object_.category_id:
                        raise ValueError("MVP 关系端点须属于同一二级品类")
                    category_key = next((key for key, identifier in tree.get("category_keys", {}).items() if identifier == subject.category_id), None)
                    binding = self.catalog.active(scope_id, category_key)
                    ranges = {slot.range for slot in binding.schema_view.class_induced_slots(binding.root_class)}
                    relation_class = next(slot.range for slot in binding.schema_view.class_induced_slots(binding.root_class) if slot.name == "relations")
                    predicate = next(slot for slot in binding.schema_view.class_induced_slots(relation_class) if slot.name == "predicate")
                    enum = binding.schema_view.get_enum(predicate.range)
                    if subject.kind not in ranges or object_.kind not in ranges or enum is None or relation.predicate not in enum.permissible_values:
                        raise ValueError("关系不符合当前启用 schema")
        if kind == "ontology":
            costs = {}
            for item in items:
                if item.kind not in {"InternalCost", "PricingStrategy"}:
                    continue
                key = (item.kind, item.label, item.category_id, item.scope.model_dump_json(),
                       *(item.properties.get(field) for field in ("cost_type", "currency", "tax_basis", "amount_basis")))
                amount = item.properties.get("amount_text")
                if amount and key in costs and costs[key] != amount:
                    raise ValueError("同一口径金额冲突，须人工补充来源并处理")
                if amount:
                    costs[key] = amount

    @business_write
    def publish(self, identity, kind, batch_id):
        authorize(identity, identity.scope_id, "publish")
        with self._lock:
            batch = self.store.read_change_batch(identity.scope_id, batch_id)
            if batch is None or batch.kind != kind:
                raise KeyError("批次不存在")
            previous = self.store.read_version(identity.scope_id, kind, "pub-" + batch.id)
            if previous:
                if batch.status != "PUBLISHED":
                    batch.status = "PUBLISHED"
                    batch.audit = previous.payload["review_audit"]
                    self.store.save_change_batch(identity.scope_id, batch)
                return previous
            pair = self._pair(identity, batch.base_versions)
            if set(batch.candidate_ids) != set(batch.decisions):
                raise ValueError("仍有未审核候选")
            payload = self._apply(batch, pair)
            self._validate(identity.scope_id, kind, payload, pair)
            if kind == "ontology":
                payload["tree_version"] = pair["tree"].id
            self._audit(batch, identity, "publish", snapshot_id="pub-" + batch.id)
            payload["review_audit"] = batch.audit
            snapshot = PublishedSnapshot(id="pub-" + batch.id, kind=kind, payload=payload,
                                         previous_id=pair[kind].id, created_by=identity.account_id)
            self.store.publish(identity.scope_id, kind, snapshot, pair[kind].id, expected_versions=batch.base_versions)
            batch.status = "PUBLISHED"
            self.store.save_change_batch(identity.scope_id, batch)
            return snapshot
