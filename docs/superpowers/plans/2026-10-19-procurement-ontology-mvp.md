# 采购本体知识服务 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**执行状态：** 用户已选择使用 `superpowers:executing-plans` 在当前任务逐项实施，并在文档交付后明确继续。规划提交已合入 `D:/Code/ontogpt` 的 `main`，产品实现继续在独立工作树进行。各 Task 的复选框和执行记录反映实际进度，未勾选任务尚未完成。

**Goal:** 交付甲乙双方独立的电脑二级品类知识服务，完成模型提取、人工审核、版本发布、企业本体与三级树可视化编辑、授权查询和 Agent 问答。

**Architecture:** `services/procurement_ontology/` 承担身份、治理与查询，SQLite 保存账号和启用 schema 指针，Fuseki/TDB2 的平台及企业数据集保存各自版本化知识。React 前端只经 FastAPI 管理 API 操作，MCP 与 LangGraph Agent 复用同一只读查询服务；运行中的 OntoGPT Web 演示保持独立。

**Tech Stack:** Python 3.10+、现有 OntoGPT/LinkML/Pydantic、FastAPI、SQLite、RDFLib、Apache Jena Fuseki/TDB2（Ubuntu WSL Docker）、MCP Python SDK、LangGraph、React、TypeScript、Vite、Cytoscape.js、pytest、Vitest。

**Spec:** `docs/superpowers/specs/2026-10-19-procurement-ontology-mvp-design.md`

**设计细节：** [目录结构](../../procurement-ontology/directory-structure.md)、[系统架构](../../procurement-ontology/system-architecture.md)、[详细设计](../../procurement-ontology/detailed-design.md)、[前端设计](../../procurement-ontology/frontend-design.md)、[企业 schema](../../procurement-ontology/schemas/README.md)、[需求与验收矩阵](../../procurement-ontology/review-and-validation.md)。

## Global Constraints

- 试点仅 `test_buyer1`、`test_supplier1` 的 `电脑(台式机/笔记本)`；`media` 不在 MVP。两家各有独立 YAML、生成的 Python、说明文档、资料、树、本体和 Fuseki 数据集。
- 分类只有 `采购负责类 → 一级品类 → 二级品类` 三层；设备类型留在二级品类内部。平台通用本体和通用树只初始化新企业，既有企业不自动同步。
- 企业画布只编辑本企业业务本体；三级树只在独立树形菜单编辑；画布及树菜单均不编辑 LinkML schema。平台管理员只管理平台通用本体和通用树，不能读写企业业务知识。
- 模型提取只产生带来源位置的候选；无可定位依据的建议不可发布。模拟文档中的成本、报价和中标结果必须保留模拟及项目范围，不能写成真实企业事实或品类默认约束。
- Schema 草案只允许新增字段/关系；YAML 经 Git 审阅、生成、测试、部署后，再由目标企业审核人运行 `activate-schema <公司> <二级品类> <版本>`。SQLite 指针和审计须同事务提交。
- Fuseki 是业务知识权威库；发布快照与当前指针必须经真实 TDB2 原子性及回滚验证后才能启用。普通查询只读本企业当前完整发布版，历史版不可改。
- JSON API、MCP 和固定为 `test_buyer1 / 电脑(台式机/笔记本)` 的 LangGraph Agent 共用授权查询服务。岗位/角色的条目级限制仅预留可空 `access_policy_ref`，MVP 不执行。
- 前端使用项目 `DESIGN.md` 和语义 CSS tokens 实现 Claude 参考风格；不加入实时换肤。新建或修改的项目文档用简体中文，保留标识符原文。

## Review Focus

- 同一来源摘录出现多次时，位置不唯一的模型候选留待补证，不能任意绑定一处；Task 7 的测试覆盖。
- 甲乙或平台账号猜测其他数据域的 ID、提交伪造 `company_id`、沿关系访问时，不返回对方条目、计数或来源；Task 10 的 API/MCP 测试覆盖。
- 分类节点被已发布本体引用时，删除请求拒绝且当前树不变；Task 8 的发布测试覆盖。
- 发布请求在写入中途失败或并发读取时，只观察到旧版或完整新版；Task 2 和 Task 4 的真实 Fuseki 测试覆盖。
- 新 schema 部署后但激活前，旧抽取任务仍固定旧版本；激活失败不能留下指针或审计的半更新；Task 6 和 Task 7 的测试覆盖。

## File Map

各 Task 的 **Files** 中，未带仓库顶层前缀的 `procurement_ontology/`、`tests/` 路径均相对 `services/procurement_ontology/`；前端 `src/` 路径均相对 `frontend/procurement-ontology/`。

| 位置 | 职责 |
| --- | --- |
| `services/procurement_ontology/procurement_ontology/models.py` | 来源、候选、树、业务条目和版本契约。 |
| `identity.py`、`schema_catalog.py` | SQLite 账户/会话/启用指针及受控 schema 解析；仅这两处写管理库。 |
| `store.py`、`rdf_codec.py` | 具名图映射、平台/企业数据集与不可变快照的 Fuseki 操作。 |
| `intake.py`、`extraction.py`、`schema_draft.py` | 原文修订、企业 schema 模型提取、缺口草案与确定性生成。 |
| `governance.py`、`query.py` | 审核、树/本体发布、企业范围内的搜索及详情。 |
| `api.py`、`mcp_server.py`、`agent.py` | HTTP、MCP、LangGraph 薄入口；均不自行访问其他企业图。 |
| `frontend/procurement-ontology/src/` | 工作区、树菜单、企业画布、审核与 Agent 测试页。 |
| `deploy/fuseki/`、`services/procurement_ontology/tests/` | 本项目独立部署、单元/真实 Fuseki/贯通测试。 |

---

### Task 1: 服务骨架与领域契约

**Files:** Create `services/procurement_ontology/pyproject.toml`, `procurement_ontology/__init__.py`, `procurement_ontology/models.py`, `tests/unit/test_models.py`（后三者均在该服务目录下）。

**Interfaces:** `SourceRevision(id, scope_id, text, sha256, simulated, submitted_by, created_at)`、`SourceSpan(revision_id, start, end, quote)`、`CategoryNode(id, level, parent_id, label)`、`KnowledgeItem(id, kind, label, description, category_id, scope, source_spans, access_policy_ref=None)`、`KnowledgeRelation(id, subject_id, predicate, object_id, source_spans, scope)`、`Candidate(id, item, status)`、`PublishedSnapshot(id, kind, payload, previous_id)` 为 Pydantic 模型；`scope_id` 为服务端数据域，条目 `scope` 为业务适用范围，`Candidate.status` 区分待审候选与无依据的 `MODEL_SUGGESTION`。其余运行和版本元数据按详细设计实现。

- [x] 写 `test_span_matches_source` 和 `test_category_level_is_one_to_three`：`assert span.quote == text[span.start:span.end]`，非法层级须抛校验错误；`access_policy_ref` 默认 `None`。
- [x] 运行新测试确认失败：独立环境安装期间先用现有解释器及服务 PYTHONPATH 观察到 9 项缺少模型的失败，替代命令记入执行记录。
- [x] 实现最小契约和独立服务依赖；根仓库通过可编辑本地依赖复用 OntoGPT，不改现有 Web 演示。
- [x] 使用计划标准 uv 命令和服务全套测试复核，9 项通过；提交本任务文件。

### Task 2: WSL Fuseki 与发布原子性前提

**Files:** Create `deploy/fuseki/compose.yaml`, `deploy/fuseki/README.md`, `services/procurement_ontology/tests/integration/test_fuseki_atomicity.py`.

**Interfaces:** 固定 Fuseki 镜像版本及项目独立持久卷；测试仅在显式 `FUSEKI_TEST_URL` 存在时运行。一次受控更新写入新版本具名图和当前指针；该实测方法供 Task 4 复用。

- [x] 写 `test_failed_update_keeps_old_pointer`、`test_concurrent_reads_see_complete_version`，并增加并发条件写入和匿名访问反例。
- [x] 部署前测试确认端点未启动而失败；Ubuntu WSL Docker 启动独立容器，记录固定镜像、3032 端口、持久卷和 Windows 连通性。
- [x] 真实 TDB2 单次条件更新实测通过：写入后运行时失败完整回滚，并发读取只见完整版本，同基础版只有一个发布生效。
- [x] 真实事务测试 4 项通过，含 Fuseki 的服务测试合计 32 项通过；提交配置及操作说明，其他现有容器和卷未变更。

### Task 3: 账号、企业数据域与会话

**Files:** Create `services/procurement_ontology/procurement_ontology/identity.py`, `tests/unit/test_identity.py`.

**Interfaces:** `IdentityStore(sqlite_path)` 提供 `bootstrap_admin(credentials)`, `create_company(id, actor)`, `create_account(company_id, role, credentials, actor)`, `authenticate(credentials) -> Identity`；`authorize(identity, scope_id, action) -> None` 执行数据域检查。`bootstrap_admin` 只在没有平台管理员时可用。创建企业/账号显式接收服务端已认证操作者；平台只能在初始化时创建首个企业管理员。`Identity` 带不可由请求覆盖的 `scope_id`（`platform` 或企业 ID）和角色。

- [x] 写 `test_bootstrap_admin_is_one_time`、`test_identity_scope_is_server_owned`、`test_platform_cannot_read_company_knowledge`：`assert identity.scope_id == "test_buyer1"`，重复初始化、伪造目标企业和平台访问企业知识均被拒绝；凭据明文不出现在 SQLite。
- [x] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_identity.py -q`，观察 13 项缺少身份实现的失败。
- [x] 实现 SQLite 账户/会话存储、密码散列、权限检查和一人一企业绑定；保留企业开通审计。
- [x] 重跑测试 13 项通过，服务全套 22 通过、4 项真实 Fuseki 测试尚未配置时跳过；提交本任务文件。

### Task 4: Fuseki 数据集、版本与新企业初始化

**Files:** Create `services/procurement_ontology/procurement_ontology/store.py`, `rdf_codec.py`, `platform_seed.py`, `tests/integration/test_store.py`.

**Interfaces:** `bootstrap_platform(store) -> None` 幂等创建空的通用本体初始版与通用三级树初始版，树的试点路径取自已有甲方候选文档 `IT与通讯 → 办公设备 → 电脑(台式机/笔记本)`；`FusekiStore.provision_company(company_id, platform_versions) -> None` 幂等地从平台已发布本体/树创建独立企业初始快照及其来源闭包，重写企业内部 ID；`append_source`、`append_candidates`、`read_batch`、`read_current(scope_id, kind)`、`publish(scope_id, kind, snapshot, expected_version)` 只操作服务端选择的数据集。`scope_id` 为平台或企业，绝不接受浏览器自报范围。

- [x] 写企业独立复制、幂等重试、来源/候选往返、发布失败和并发反例，并补充复制来源闭包及 RDF 关系来源可查询测试。
- [x] 运行初始测试观察缺少存储实现的失败；关系来源联查测试在补充 RDF reification 前明确失败。
- [x] 实现具名图映射、平台及企业数据集开通、来源/候选往返和已验证的发布事务；普通读只取完整当前快照。
- [x] 真实存储集成测试 8 项通过；含真实 Fuseki 的全部服务测试 40 项通过；提交本任务文件。

### Task 5: 甲乙独立 schema 与只读加载

**Files:** Create `src/ontogpt/templates/company/general_template/README.md`, `src/ontogpt/templates/company/test_buyer1/computer/v1/test_buyer1_computer.{yaml,py}`, `src/ontogpt/templates/company/test_supplier1/computer/v1/test_supplier1_computer.{yaml,py}`, `services/procurement_ontology/schema_registry.yaml`, `procurement_ontology/schema_loader.py`, `tests/unit/test_schema_loader.py`；modify 根 `pyproject.toml` 的嵌套模板打包配置，核对已编写的 `docs/procurement-ontology/schemas/{test_buyer1,test_supplier1}/computer/v1.md`。

**Interfaces:** `load_registered_template(company_id, category_key, version) -> TemplateBinding` 返回 YAML、已生成 Python、根类、SHA-256、生成器/导入依赖摘要与 `SchemaView`；甲乙根类分别为 `BuyerComputerExtraction`、`SupplierComputerExtraction`，不调用现有 `get_template_details(custom.yaml)` 的根目录复制与运行时生成路径。

- [x] 写 `test_buyer_supplier_have_distinct_files`、`test_nested_import_and_hash`、`test_installed_template_artifacts`：两套路径不同，根类可解析，生成模块可导入，文件及导入依赖校验值匹配；篡改文件则拒绝加载；wheel 安装后仍包含并可加载两套嵌套模板。
- [x] 运行新测试观察到 5 项缺少加载器的失败；追加依赖摘要测试观察到篡改依赖未被拒绝的失败。
- [x] 依据甲乙模拟原文分别写最小 LinkML 字段、关系；LinkML 连续两次生成结果一致，登记产物及依赖摘要。`general_template` 仅作编写参考。
- [x] 加载/安装产物测试 6 项通过；实际调用现有模板枚举函数确认 66 个演示模板不含企业模板；提交本任务文件。

### Task 6: SQLite schema 激活命令

**Files:** Create `services/procurement_ontology/procurement_ontology/schema_catalog.py`, `cli.py`, `tests/unit/test_schema_activation.py`.

**Interfaces:** `SchemaCatalog.active(company_id, category_key) -> TemplateBinding`；`activate_schema(identity, company_id, category_key, version) -> ActivationRecord` 验证目标企业、部署文件/哈希、根类和生成模块，在一个 SQLite 事务中更新指针与操作者/时间审计。CLI 暴露 `activate-schema <公司> <二级品类> <版本>`。

- [ ] 写 `test_activation_is_atomic`、`test_wrong_company_and_missing_artifact_fail`：`assert active.version == "v1"` 只在审计也增加后成立；失败时两表行数及指针不变。
- [ ] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_schema_activation.py -q`，期望失败。
- [ ] 实现受控激活命令与事务；测试运行中已取得的 `TemplateBinding` 不随指针切换改变。
- [ ] 重跑测试，期望通过；提交本任务文件。

### Task 7: 原文修订、实际模型提取与证据定位

**Files:** Create `services/procurement_ontology/procurement_ontology/intake.py`, `extraction.py`, `tests/unit/test_extraction.py`, `tests/fixtures/supplier-laptop-bid-case.md`；沿用仓库根的 `tests/fixtures/procurement/laptop-purchase-case.md`。

**Interfaces:** `IntakeService.submit(identity, text, simulated) -> SourceRevision`；`ExtractionService.extract(identity, revision_id, category_key) -> ExtractionRun` 固定当前启用 schema 的版本/哈希，通过仓库现有 `SPIRESEngine` 提取，再把输出映射为候选、关系与原文 `SourceSpan`。模型连接从服务配置取得。

- [ ] 写 `test_buyer_and_supplier_use_own_schema`、`test_ambiguous_quote_stays_unverified`、`test_original_unicode_offsets`、`test_retry_keeps_one_run`：两份原文各绑定自己的 schema；重复摘录无唯一位置时不得形成可发布事实；中文、换行与非 BMP 字符的摘录仍定位到原文；任务开始后的指针变化不改本次版本。
- [ ] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_extraction.py -q`，期望失败。
- [ ] 从用户提供的乙方模拟案例复制测试资料并保留模拟标记；实现来源校验、抽取失败状态和重试去重；模型输出不得直接发布。
- [ ] 重跑替身模型测试，期望通过；提交本任务文件。真实模型调用留在 Task 15 贯通验收单独记录。

### Task 8: 审核、企业/平台版本发布与授权查询

**Files:** Create `services/procurement_ontology/procurement_ontology/governance.py`, `query.py`, `tests/integration/test_governance_query.py`.

**Interfaces:** `GovernanceService.review(identity, candidate_id, decision)`、`edit_item(identity, change, observed_version)`、`edit_tree(identity, change, observed_version)`、`publish(identity, kind, batch_id)`；`KnowledgeQuery.search(identity, text, category_key)` 与 `get(identity, item_id, observed_version=None)` 仅读本企业当前已发布版。`observed_version` 携带树和本体版本对，平台通用本体/树只能经平台身份编辑并发布。

- [ ] 写 `test_unpublished_is_invisible`、`test_referenced_category_cannot_be_deleted`、`test_platform_and_company_write_scopes`、`test_observed_version_conflict`、`test_cost_conflict_is_not_silently_overwritten`：未审候选不可查，删被引用节点失败，平台不能改企业，树或本体换版后详情返回版本变化；600/1,200 元冲突不能静默覆盖。
- [ ] 使用 Fuseki 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/integration/test_governance_query.py -q`，期望失败。
- [ ] 实现审核轨迹、来源/范围/关系/唯一父级校验、待审批次和不可变发布；树节点先发布后才能被新本体引用，查询返回来源片段和实际版本。
- [ ] 重跑集成测试，期望通过；提交本任务文件。

### Task 9: 自动发现 schema 缺口并起草新版本

**Files:** Create `services/procurement_ontology/procurement_ontology/schema_draft.py`, `tests/unit/test_schema_draft.py`, `docs/procurement-ontology/schemas/README.md`；modify `services/procurement_ontology/procurement_ontology/extraction.py`.

**Interfaces:** `ExtractionRun.unmapped_suggestions` 保留模型从资料或用户陈述中发现的未映射信息；`detect_gap(binding, source_span, proposed_field_or_relation) -> SchemaGap`；`draft_additive_schema(gap, draft_worktree) -> DraftArtifacts` 验证该工作树处于待审 schema 草案分支，只向新版本目录写 YAML，并用 LinkML 生成 Python；不修改当前版本、注册表部署项或 SQLite 指针。

- [ ] 写 `test_new_relation_generates_draft`、`test_rename_or_type_change_is_rejected`、`test_wrong_git_branch_is_rejected`：资料触发的建议生成企业专属可解析 `v2` YAML/Python，`v1` 哈希和启用指针不变；删除/重命名/跨企业关系及错误工作树拒绝。
- [ ] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_schema_draft.py -q`，期望失败。
- [ ] 实现自然语言/资料触发的缺口记录、仅增加字段/关系的确定性约束和草案生成；文档写明 Git 审阅、测试、部署与 `activate-schema` 的分界。
- [ ] 重跑测试，期望通过；提交本任务文件。

### Task 10: 管理 JSON API 与 MCP 查询工具

**Files:** Create `services/procurement_ontology/procurement_ontology/api.py`, `mcp_server.py`, `tests/unit/test_api_mcp.py`.

**Interfaces:** `create_app(...) -> FastAPI` 提供登录、企业开通、来源提交/抽取、自然语言 schema 缺口提交与草案状态、审核、树/本体变更与发布、schema 激活状态、`GET /v1/ontology/items`、`GET /v1/ontology/items/{id}`。企业开通按 Task 4 幂等顺序创建独立数据集及 SQLite 账户。MCP 仅提供 `search_ontology_items` 和 `get_ontology_item`，调用同一个 `KnowledgeQuery`。

- [ ] 写 `test_tenant_override_is_ignored`、`test_platform_cannot_read_company`、`test_company_provision_retry`、`test_mcp_api_parity`：伪造企业参数、猜 ID、关系路径和计数均不能越界；开通重试不重复实例化；同身份 API/MCP 返回同一版本及来源；MCP 无写工具。
- [ ] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_api_mcp.py -q`，期望失败。
- [ ] 实现同源会话认证、管理 API 与薄 MCP 适配，浏览器和 Agent 均不直连 Fuseki；错误响应不暴露他企是否存在。
- [ ] 重跑测试，期望通过；提交本任务文件。

### Task 11: 前端工作区、树菜单与平台入口

**Files:** Create `frontend/procurement-ontology/package.json`, `vite.config.ts`, `DESIGN.md`, `src/styles/tokens.css`, `src/api.ts`, `src/App.tsx`, `src/TreeEditor.tsx`, `src/PlatformEditor.tsx`, `src/App.test.tsx`.

**Interfaces:** `api.ts` 使用同源会话调用 Task 10 API；企业工作区只显示自身资料、审核、树菜单和本体画布，固定甲方问答入口仅对获准甲方账号显示；平台工作区只显示通用本体及通用树管理。树编辑组件提交节点/父子关系的变更操作和所见版本。

- [ ] 写 `test_company_only_sees_own_workspace`、`test_platform_has_no_company_routes`、`test_tree_editor_rejects_fourth_level`：断言菜单项与提交 API 路径按身份分域，第四层不产生写请求。
- [ ] 运行 `npm test --prefix frontend/procurement-ontology -- --run`，期望失败。
- [ ] 实现 React/Vite 最小页面、Claude 参考 `DESIGN.md` 与语义 tokens、资料/审核/发布、自然语言缺口提交与草案状态、树形 CRUD 和平台通用本体的最小属性编辑入口；服务端仍执行最终授权与校验。
- [ ] 重跑前端测试和 `npm run build --prefix frontend/procurement-ontology`，期望通过；提交本任务文件。

### Task 12: 企业业务本体画布

**Files:** Create `frontend/procurement-ontology/src/OntologyCanvas.tsx`, `src/canvasChanges.ts`, `src/OntologyCanvas.test.tsx`；只按需要修改 `src/App.tsx` 和 `src/styles/tokens.css`。

**Interfaces:** Cytoscape.js 接收服务端按企业、品类、发布版裁剪的节点/边及待审覆盖层；`toChange(selected, operation, observed_version)` 只生成条目/关系操作，不产生分类树或 LinkML 修改。右侧属性面板显示范围、来源和模拟标记。

- [ ] 写 `test_canvas_emits_item_relation_changes_only`、`test_stale_version_prompts_refresh`：断言操作带所见版本和来源；分类节点编辑按钮不存在；已部署但未激活的新关系不能提交；409 不覆盖当前服务端图。
- [ ] 运行 `npm test --prefix frontend/procurement-ontology -- --run`，期望失败。
- [ ] 实现局部图、连线关系类型选择、增改移除及差异预览；所有保存进入待审批次，颜色与节点样式从语义 tokens 读取。
- [ ] 重跑前端测试与构建，期望通过；提交本任务文件。

### Task 13: LangGraph Agent 与浏览器问答页

**Files:** Create `services/procurement_ontology/procurement_ontology/agent.py`, `tests/unit/test_agent.py`, `frontend/procurement-ontology/src/AgentPage.tsx`, `src/AgentPage.test.tsx`；只按需要修改 `api.py`、`App.tsx`。

**Interfaces:** `answer_laptop_question(question) -> AgentAnswer` 在服务端固定 `test_buyer1 / 电脑(台式机/笔记本)`，仅调用 `KnowledgeQuery.search/get`；返回答案、实际工具引用的条目 ID、来源片段和本体版本。浏览器页只有提问及这些结果。

- [ ] 写 `test_agent_uses_fixed_scope_and_citations`、`test_supplier_cannot_open_buyer_agent`、`test_no_evidence_says_no_evidence` 和前端引用显示测试：只有甲方测试账号能调用固定甲方 Agent；请求携带他企 ID 不改变范围；没有工具命中不得编造来源。
- [ ] 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/unit/test_agent.py -q` 与前端测试，期望失败。
- [ ] 实现最小 LangGraph 搜索→详情→回答流程及问答页；服务端从工具实际输出整理引用，不接受模型自报的 ID。
- [ ] 重跑两端测试与前端构建，期望通过；提交本任务文件。

### Task 14: SQLite/Fuseki 双备份与恢复

**Files:** Create `services/procurement_ontology/procurement_ontology/backup.py`, `tests/integration/test_recovery.py`, `services/procurement_ontology/README.md`.

**Interfaces:** `backup_service(destination) -> BackupManifest` 在阻止新写入的维护窗口内备份 SQLite 与平台/企业 Fuseki 数据集，记录文件校验值；`restore_service(manifest, target) -> None` 校验完整性后恢复两者。不得把密钥或持久卷提交 Git。

- [ ] 写 `test_restore_keeps_pointer_source_history_and_audit`、`test_incomplete_backup_is_rejected`、`test_backup_blocks_new_writes`：恢复后当前/历史快照、来源、schema 指针及操作者审计一致；缺任一数据集或 SQLite 文件拒绝恢复；备份窗口内新写入被拒绝。
- [ ] 使用真实 Fuseki 运行 `uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/integration/test_recovery.py -q`，期望失败。
- [ ] 实现维护窗口备份、校验和恢复命令及中文操作说明；只处理本项目数据集和 SQLite 文件。
- [ ] 重跑恢复测试，期望通过；提交本任务文件。

### Task 15: 本地贯通验收与证据

**Files:** Create `services/procurement_ontology/tests/integration/test_acceptance.py`；modify `services/procurement_ontology/README.md`，仅为贯通缺口修改前述任务文件。

**Interfaces:** 复用 Tasks 1–14；无新生产抽象。按需求与验收矩阵检查平台初始化、两企业模拟资料经真实模型提取、候选审核、树和本体发布、查询、schema 起草/激活、画布变更、Agent、重启和双备份恢复。

- [ ] 写 `test_buyer_supplier_end_to_end`：断言甲乙各自模型候选经审核才可查、模拟/项目范围保留、乙方成本只在乙方可见、平台更新不改老企业、API/MCP/Agent 版本一致。
- [ ] 用真实 Fuseki 运行贯通测试，修复阻塞该测试的最小集成缺口；记录故障注入与并发发布结果。
- [ ] 用已配置的真实模型分别抽取甲乙材料，并在浏览器以甲方、乙方、平台三类账号实操树菜单、画布、问答及越权场景；无模型凭据或浏览器证据时明确标为未验证，不记为通过。
- [ ] 验证重启和备份恢复后指针、来源、历史及审计完整；运行服务测试、前端测试/构建、`git diff --check`，把实际命令及结果写入中文 README；提交验收记录。

## 执行边界

本计划以每个 Task 的测试与提交作为复核点。Task 2 的真实 TDB2 原子性未通过前，Task 8 不启用发布；Task 15 的真实模型、浏览器和恢复证据缺一项时，只报告对应未验证项，不宣称 MVP 完成。旧计划 `docs/superpowers/plans/2026-10-16-procurement-ontology-knowledge-service.md` 保留为历史资料，不作为本次执行依据。
