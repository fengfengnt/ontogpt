# 采购本体知识服务 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在本仓库交付可运行的独立知识服务，让甲乙两家试点企业把有来源的候选知识审核发布，再经授权的 JSON API 和 MCP Tools 查询。

**Architecture:** `services/procurement_ontology/` 单独打包；FastAPI 负责管理和读取，SQLite 管账户与服务身份，Jena Fuseki/TDB2 为各企业保存来源、候选和不可变发布版本。读取 API 与 MCP 共用同一查询服务；模拟笔记本案例先导入候选，不自动成为真实企业事实。

**Tech Stack:** Python 3.10+、FastAPI、Pydantic 2、httpx、RDFLib、SQLite 标准库、Apache Jena Fuseki/TDB2、MCP Python SDK、pytest；本地联调直接运行 Fuseki，无 Docker 前提。

**Spec:** `docs/superpowers/specs/2026-10-16-procurement-ontology-knowledge-service-design.md`

## Global Constraints

- 不修改 `src/ontogpt/webapp/`；服务位于 `services/procurement_ontology/`，试点先支持一家甲方和一家乙方，但按企业隔离。
- 分类固定为 `采购负责类 → 一级品类 → 二级品类`；“笔记本电脑”只是二级品类 `电脑(台式机/笔记本)` 的设备类型。
- 知识候选须有可定位来源；模型无原文支撑的内容只作 `MODEL_SUGGESTION`；模拟案例和常识建议不得自动成为已发布企业事实。
- 每企业最多一个待发布分类树批次、一个待发布业务本体批次；树和本体独立发布，业务本体不得引用未发布树节点；旧版本不可改。
- 普通搜索与详情仅读最新已发布视图，并以服务端身份决定企业；未授权企业和私有来源不得经 ID 或关系路径泄漏。
- 首期只提供知识搜索与按 ID 读取两项 MCP Tools；不实现采购判定、入围、Agent 对话、RDF/OWL 文件交换或开放 SPARQL。
- 新建或修改的项目文档使用简体中文，保留代码标识符、API 字段和标准术语原文。

## Review Focus

- 跨租户直接猜 ID 或在关联路径绕入另一企业时，不返回对方条目和片段；任务 7 用 API 权限测试覆盖。
- 两份来源支持同一条事实时保留两份来源引用，不复制为两条事实；任务 3 用存储往返测试覆盖。
- 模拟案例条目含“100 台”“16GB”等本次取值时，不把数值提升为通用默认硬约束；任务 5 用导入测试覆盖。
- 发布过程中 Jena 写入失败时，当前指针仍指旧版且旧版可查询；任务 6 用故障注入测试覆盖。
- 搜索到 ID 后发生新发布，详情请求带旧观察版本时明确报告版本变化；任务 7 用并发版本测试覆盖。

---

### Task 1: 独立服务与知识契约

**Files:** Create `services/procurement_ontology/pyproject.toml`, `services/procurement_ontology/procurement_ontology/models.py`, `services/procurement_ontology/procurement_ontology/__init__.py`, `services/procurement_ontology/tests/test_models.py`.

**Interfaces:** Define `SourceRevision`, `SourceSpan`, `CategoryNode`, `KnowledgeItem`, `Candidate`, `PublishedVersion` as Pydantic models. `KnowledgeItem` fields include stable `id`, `kind`, `label`, `description`, `category_id`, `scope`, `valid_from`, `valid_to`, `source_span_ids`, `relations`, and optional `example_value`; case examples never populate `default_value` implicitly. Later tasks import these names.

- [ ] Write `test_category_has_exactly_one_parent_below_root`, `test_item_keeps_example_separate_from_default`, `test_candidate_without_locatable_span_is_suggestion`; assert invalid tree shape and source-less fact are rejected.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_models.py -q`; expect red.
- [ ] Implement the minimal models and dependency declaration; use enums only for the five generic candidate forms (`Class`, `Property`, `Relation`, `Constraint`, `Instance`) and concrete knowledge-item forms needed by the spec.
- [ ] Rerun the same command; expect green. Commit only Task 1 files.

### Task 2: 身份、企业与权限

**Files:** Create `services/procurement_ontology/procurement_ontology/identity.py`, `services/procurement_ontology/tests/test_identity.py`.

**Interfaces:** `IdentityStore(sqlite_path)` offers `create_company`, `create_account`, `issue_service_token`, `authenticate` and `require_permission(identity, company_id, permission)`. `bootstrap_admin(sqlite_path, username, password)` initializes the first platform admin only when none exists. Store salted password hashes with `hashlib.scrypt`; store service-token digests, never raw tokens. Role permissions: platform admin creates companies, company admin grants company roles and publishes, reviewer reviews, source editor submits, reader reads. HTTP task consumes an `Identity` with server-resolved `company_id` and permissions.

- [ ] Test one-time platform-admin bootstrap, company/admin creation, an enterprise reader seeing own company, and rejected cross-company access even when caller passes a different ID; test that DB does not contain plaintext passwords/tokens.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_identity.py -q`; expect red.
- [ ] Implement SQLite schema, `scrypt` authentication, token digest lookup and permission checks without a separate RBAC framework.
- [ ] Rerun that command; expect green. Commit Task 2 files.

### Task 3: 企业独立的 Fuseki 存储

**Files:** Create `services/procurement_ontology/procurement_ontology/store.py`, `services/procurement_ontology/procurement_ontology/rdf.py`, `services/procurement_ontology/tests/test_store.py`, `services/procurement_ontology/tests/conftest.py`.

**Interfaces:** `FusekiStore(base_url, admin_identity)` provisions one TDB2 dataset per enterprise; `put_source(company_id, SourceRevision)`, `put_candidates(company_id, batch_id, list[Candidate])`, `read_batch(company_id, batch_id)`, `read_current(company_id)`, `read_version(company_id, version_id)` and `publish_snapshot(company_id, kind, snapshot, expected_version)` call a single transaction-safe Fuseki operation for the version graph plus current pointer. `rdf.py` maps model objects to stable IRIs and named graphs; include source-span links and deterministic round trips. Do not expose generic SPARQL to HTTP callers.

- [ ] Test separate buyer/supplier datasets, identical fact with two source spans, source and candidate round trip, and snapshot/current-pointer transaction against locally launched Fuseki; use a test fixture that skips only when its explicit `FUSEKI_TEST_URL` is absent.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_store.py -q` with `FUSEKI_TEST_URL` set; expect red.
- [ ] Implement RDF mapping and Jena HTTP calls; keep Fuseki reachable only through service configuration, never from browser or Agent.
- [ ] Rerun with Fuseki; expect green. Commit Task 3 files.

### Task 4: 来源导入与通用候选提取

**Files:** Create `services/procurement_ontology/procurement_ontology/intake.py`, `services/procurement_ontology/procurement_ontology/extraction.py`, `services/procurement_ontology/tests/test_intake.py`.

**Interfaces:** `IntakeService.submit_text(identity, text, source_metadata)` and `submit_markdown(identity, filename, content)` write immutable source revisions. `Extractor.extract(SourceRevision) -> list[Candidate]` accepts a replaceable LLM caller and returns five generic candidate forms with exact source spans; `IntakeService.extract_revision(revision_id)` deduplicates retries by source revision plus candidate meaning. Unanchored model output becomes `MODEL_SUGGESTION` and cannot be confirmed.

- [ ] Mock LLM output with anchored `Class`/`Constraint` and an unanchored suggestion; assert line/offset provenance, immutable source revision, duplicate retry suppression and source persistence on extraction failure.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_intake.py -q`; expect red.
- [ ] Implement intake, the minimal OpenAI-compatible extraction call, strict span validation and retry behavior; record provider error without publishing knowledge.
- [ ] Rerun that command; expect green. Commit Task 4 files.

### Task 5: 试点知识包作为模拟候选

**Files:** Create `services/procurement_ontology/procurement_ontology/sample.py`, `services/procurement_ontology/tests/test_sample.py`; use existing `docs/procurement-ontology/laptop-knowledge-pack-candidate-v0.md` and `tests/fixtures/procurement/laptop-purchase-case.md` read-only.

**Interfaces:** `build_laptop_sample(case_text, candidate_doc) -> list[Candidate]` creates the three category nodes and laptop-scoped `CollectionField`, `SupplierConditionTemplate`, and explanatory entries; each supported item references a case line or explicit user amendment. `load_laptop_sample(identity, intake_service, case_path, candidate_path)` writes them as pending source/candidate records, never as published knowledge. `MODEL_SUGGESTION` entries remain separate. Provide a tiny supplier fixture through the same `IntakeService` path so tenant querying can be exercised.

- [ ] Assert `电脑(台式机/笔记本)` is leaf level three, `设备类型=办公笔记本`, case line anchors resolve, `100 台`/`16GB` stay examples, suggestions remain unpublished candidates, and supplier data stays in its own tenant.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_sample.py -q`; expect red.
- [ ] Implement a deterministic import of the checked-in candidate document; fail on missing case anchors instead of inventing facts.
- [ ] Rerun that command; expect green. Commit Task 5 files.

### Task 6: 审核、校验与不可变发布

**Files:** Create `services/procurement_ontology/procurement_ontology/governance.py`, `services/procurement_ontology/tests/test_governance.py`.

**Interfaces:** `GovernanceService.review(identity, batch_id, candidate_id, decision, revised_item=None)` accepts/rejects a candidate; `edit_graph_item` saves a confirmed revision into the current pending batch; `publish_tree(identity, batch_id)` and `publish_ontology(identity, batch_id)` validate and call `FusekiStore.publish_snapshot`. Each publish produces an immutable full snapshot with author, time, source batch and previous version ID. One open batch per company and kind.

- [ ] Test pre-publication invisibility, all items reviewed before publication, dependency closure, unique tree parent, missing source, overlap conflict, ontology referencing unpublished category, batch uniqueness, successful old/new versions and injected write failure preserving old current pointer.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_governance.py -q` with Fuseki; expect red.
- [ ] Implement batch state machine and structural checks; publish new tree before its dependent ontology; use store transaction, not multi-request pointer updates.
- [ ] Rerun that command; expect green. Commit Task 6 files.

### Task 7: 授权 JSON API 与最小治理页面

**Files:** Create `services/procurement_ontology/procurement_ontology/query.py`, `services/procurement_ontology/procurement_ontology/api.py`, `services/procurement_ontology/procurement_ontology/admin.py`, `services/procurement_ontology/tests/test_api.py`.

**Interfaces:** `KnowledgeQuery.search(identity, query, limit=10)` returns ID/type/summary/三级路径/current versions and up to three actual relation hops; `KnowledgeQuery.get(identity, item_id, observed_version=None)` returns detail, one-hop summaries, scope, validity and permitted source spans. `create_app(identity_store, fuseki_store) -> FastAPI` exposes `GET /v1/ontology/items?query=...` and `GET /v1/ontology/items/{item_id}` through these methods; management endpoints/pages use the same identity and governance services. Admin pages cover company/account creation, source submission, candidate list/review, graph item edit, batch diff and publish; graph uses local HTML/SVG with clickable node/edge, no external asset dependency.

- [ ] With FastAPI TestClient, assert search limit 10, latest-only output, path truthfulness, unauthorized guessed ID and relation paths reveal nothing, private supplier spans stay hidden, observed-version mismatch reports change, and admin actions reject readers.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_api.py -q`; expect red.
- [ ] Implement query and API/UI handlers; filter tenant and disclosure before search ranking/counting and before relation expansion; expose full source only to source-permitted company users.
- [ ] Rerun that command; expect green. Commit Task 7 files.

### Task 8: MCP 适配与运行恢复

**Files:** Create `services/procurement_ontology/procurement_ontology/mcp_server.py`, `services/procurement_ontology/procurement_ontology/backup.py`, `services/procurement_ontology/tests/test_mcp.py`, `services/procurement_ontology/tests/test_recovery.py`, `services/procurement_ontology/README.md`.

**Interfaces:** MCP Tools `search_ontology_items` and `get_ontology_item` delegate exactly to `KnowledgeQuery` with authenticated user or company-bound service identity. `backup_company(company_id, destination)` and `restore_company(backup, target_dataset)` use Jena-supported dataset export/import and protect current, historical, source and pending named graphs. README provides Python/Java/Fuseki startup, first admin bootstrap, sample candidate load/review, API/MCP calls, backup and restore.

- [ ] Test API/MCP parity for same identity, rejection of caller-supplied company override, and a backed-up buyer dataset restored after service restart with current version, old snapshot, pending batch and source links intact.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_mcp.py services/procurement_ontology/tests/test_recovery.py -q` with Fuseki; expect red.
- [ ] Implement two thin MCP tools, backup/restore commands and Chinese operator documentation. Verify against actual MCP Python SDK installed in the service environment.
- [ ] Rerun the tests; expect green. Commit Task 8 files.

### Task 9: 第一阶段贯通验收

**Files:** Create `services/procurement_ontology/tests/test_acceptance.py`; update `services/procurement_ontology/README.md` only for verified commands and limits.

**Interfaces:** Reuse Tasks 1–8; no new production abstraction. Test starts with both empty enterprise datasets, imports sample as candidate, reviews/publishes tree then knowledge, queries buyer and supplier through API and MCP, edits/publishes a second version, then restores from backup.

- [ ] Write acceptance test asserting candidate invisibility, office-laptop entries and exact source line, supplier tenant isolation, old version retained, latest read changed, API/MCP parity, and restored state.
- [ ] Run `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/test_acceptance.py -q` with Fuseki; expect red until every interface is wired.
- [ ] Complete only missing wiring found by the acceptance run; do not add procurement decisions or an Agent implementation.
- [ ] Run the full service test suite with Fuseki, `git diff --check`, and a manual browser pass over admin login, candidate review, graph edit and publish. Record exact pass/fail evidence in README; commit Task 9 files.

## 完成判据

两家企业的数据集与读取权限隔离；笔记本样本经过来源、候选、审核和发布全链路后可通过 JSON/MCP 查到，并正确保留模拟标签、适用设备类型与案例示例值；未发布内容、他企私有内容和旧版不会混入普通查询；历史与恢复流程可审计。若本地缺少可用的 LLM 凭据，抽取调用只做替身测试，明确记录尚未验证真实模型效果，不把它写作通过。
