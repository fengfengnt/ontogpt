# 买方、供应商 v2 Schema 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 10 份草案整合为两套已注册、可验证的 v2，保留 v1 并推送 `dev-fengfeng`。

**Architecture:** 每个企业在 v1 上累加归档定义；沿用现有注册加载、LinkML 生成和显式激活机制。应用行为与运行数据库不变。

**Tech Stack:** LinkML 1.12.1、Pydantic 2.14.1、PyYAML、pytest。

**Spec:** `docs/superpowers/specs/2026-11-08-procurement-schema-v2-design.md`

## Global Constraints

- 仅修改 `D:/Code/ontogpt`，使用 `dev-fengfeng`；暂不部署。
- 保留所有 v1 文件、注册项、归档及备份；不调用真实模型。
- 新文档使用简体中文；生成 Python 不手工编辑。

## Review Focus

- 新字段在模型验证或候选归一化过程中不能静默丢失。
- 不得加入案例默认值或把买方字段混入供应商。
- 注册 v2 不得隐式激活；旧 v1 数据与注册项不变。
- wheel 必须包含并能加载全部四套已注册模板。
- 现有激活夹具不能因真实 v2 出现而覆盖、混用或产生重复注册项。

### Task 1: 整合、验证并交付 v2

**Files:**
- Create: `src/ontogpt/templates/company/{test_buyer1,test_supplier1}/computer/v2/` 下各自 YAML/Python。
- Modify: `services/procurement_ontology/schema_registry.yaml`。
- Test: `services/procurement_ontology/tests/unit/test_schema_v2.py`。
- Modify: `services/procurement_ontology/tests/unit/test_schema_activation.py`、`test_schema_loader.py`。
- Document: `docs/procurement-ontology/schemas/v2.md` 及相关索引。

**Interfaces:**
- Consumes: `load_registered_template(company_id, category_key, version)`、`normalize_candidates(binding, source, run, extracted, category_id)`。
- Produces: 买方和供应商的 `computer/v2` 注册绑定；不修改加载或激活接口。

- [x] **Step 1:** 新增按企业参数化测试：归档定义完整、v1 不变、v2 兼容且纯新增、确定性生成、新字段类型校验和归一化保留；扩展 wheel 测试至 v1/v2。
- [x] **Step 2:** 执行新增测试，预期因 v2 未注册失败，保留 RED 证据。
- [x] **Step 3:** 从原始 YAML 累加定义并生成两套 Python，追加注册项；激活夹具直接使用真实 v1/v2，取消伪造 v2 的步骤。
- [x] **Step 4:** 执行 `services/procurement_ontology/.venv/Scripts/python.exe -m pytest -q services/procurement_ontology/tests/unit/test_schema_v2.py services/procurement_ontology/tests/unit/test_schema_activation.py services/procurement_ontology/tests/unit/test_schema_loader.py`，预期全部通过。
- [x] **Step 5:** 更新 v2 来源及使用边界文档；在服务目录执行 `.venv/Scripts/python.exe -m pytest -q`，预期无失败；外部环境依赖的跳过项明确列出。
- [ ] **Step 6:** 独立审阅全部差异，修复重要问题，核验 v1/归档/备份不变；提交命名文件并推送 `origin dev-fengfeng`，核对远端 SHA 与干净状态。不执行部署或激活。
