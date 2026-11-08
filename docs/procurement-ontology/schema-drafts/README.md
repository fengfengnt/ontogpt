# 已纳入主线的待审 Schema 草案

日期：2026-11-08。状态：**10 份原始候选完整归档、技术校验通过；业务审核仍待完成**。

这些候选原来分别位于独立工作树，均基于已启用的 `v1` 生成同名 `v2`。本次按用户确认采用“按草案 ID 保存完整待审版本”的方式，将所有原始提交历史合入 `dev-fengfeng`，并将文件移至本目录的各自 ID 下，避免不同候选互相覆盖。此前未提交的 4 份草案已先提交再合并。

每份候选仅包含一项新增字段或关系，合计 9 个字段、1 个关系；采购方 7 份、供应商 3 份。[manifest.json](manifest.json) 记录生成文件摘要、来源提交、合并提交、原始分支、来源修订 ID、原文位置与片段摘要、模拟标记及校验结果。完整原文和业务凭据不随归档提交。

## 候选索引

| 草案 ID / YAML | 企业 | 新增内容 | 来源标记 |
| --- | --- | --- | --- |
| [gap-0126891f4a24498d97b9a536791113ed](gap-0126891f4a24498d97b9a536791113ed/test_buyer1_computer.yaml) | `test_buyer1` | `ConditionTemplate.quotation_inclusions` | 未标记模拟 |
| [gap-365d6f39cb5a44309380c06c3b99269e](gap-365d6f39cb5a44309380c06c3b99269e/test_buyer1_computer.yaml) | `test_buyer1` | `CollectionField.procurement_unit_price` | 未标记模拟 |
| [gap-651ce65f78644509bf0b29507dc1557b](gap-651ce65f78644509bf0b29507dc1557b/test_supplier1_computer.yaml) | `test_supplier1` | `PricingStrategy.late_payment_penalty_text` | 模拟 |
| [gap-699aae1b42804daaa9ed0071228cf232](gap-699aae1b42804daaa9ed0071228cf232/test_buyer1_computer.yaml) | `test_buyer1` | `ProcessNote.evaluation_committee_size` | 模拟 |
| [gap-700cd6c30feb4d718fca341dfe5922ba](gap-700cd6c30feb4d718fca341dfe5922ba/test_buyer1_computer.yaml) | `test_buyer1` | `TermDefinition.brand_pool_membership` | 未标记模拟 |
| [gap-7d3a4286f5784c0295c8da7e3b0a4ef3](gap-7d3a4286f5784c0295c8da7e3b0a4ef3/test_buyer1_computer.yaml) | `test_buyer1` | `ConditionTemplate.volume_discount_tier` | 未标记模拟 |
| [gap-7d8adc44050a4534bda3d142ce3c3249](gap-7d8adc44050a4534bda3d142ce3c3249/test_supplier1_computer.yaml) | `test_supplier1` | `ProjectEvidence.invited_supplier_names` | 模拟 |
| [gap-c75c7dc1055b45c8abdebdd2378eeb36](gap-c75c7dc1055b45c8abdebdd2378eeb36/test_buyer1_computer.yaml) | `test_buyer1` | `ConditionTemplate.acceptance_inspection_ratio` | 模拟 |
| [gap-ce89ebac0e5c4e77b28010ecb3c70e5b](gap-ce89ebac0e5c4e77b28010ecb3c70e5b/test_supplier1_computer.yaml) | `test_supplier1` | `PricingStrategy.payment_terms_text` | 模拟 |
| [gap-da259bccdfcd4d40b52851a7f3874d33](gap-da259bccdfcd4d40b52851a7f3874d33/test_buyer1_computer.yaml) | `test_buyer1` | `conflicts_with` | 模拟 |

每个目录同时保存原始 YAML 和 LinkML 生成的 Python。`.gitattributes` 固定 LF，确保跨 Windows/Linux 检出后仍可按清单验证 SHA-256。

## 校验与使用边界

- 10 份候选均通过：仅新增内容的结构比较、LinkML 重新生成与原 Python 逐字节一致、Python 语法、临时注册表隔离加载及 Pydantic JSON Schema 生成检查。
- 文件摘要均与现有业务草案记录一致；来源片段通过现有 `SourceSpan.validate_against` 核验，基础 YAML/Python 与当前 `v1` 一致。
- 6 份来源标记为模拟材料；“未标记模拟”也不表示已经核实材料真实性。技术校验不替代业务审核、金额/比例单位确认、来源适用范围核对或候选取舍。
- **本目录不是运行模板目录或运行注册表。** 原始归档时没有写入运行模板目录、注册表或 SQLite 启用指针，构建器的应用白名单不包含这些待审文件。后续独立的源码整合见下文；本目录快照与清单保持不变。
- 业务草案记录保持 `DRAFT`，没有改成已审核、已发布或已启用。后续正式版本需要明确选择或整合候选、生成与回归校验、注册部署，再由企业审核人显式启用。

合并后回归：后端 **114 passed、47 skipped**（外部集成环境未配置的项目仍记为跳过），前端 **18 passed**，TypeScript/Vite 构建通过；激活相关用例单独复测 **5 passed**。本次没有修改程序源码或运行注册表。

## 旧路径、审阅与恢复

验证和推送完成后，原始草案工作树可清理。数据库不可变记录中的旧绝对路径与分支名保留为历史生成位置；现在按 `draft_id` 在本目录或清单中定位文件。管理页面显示的原文、分支名和 YAML 差异来自已保存记录，读取时不访问旧工作树文件。

原始文件在各 `source_commit` 的原位置仍可审阅，例如：

```text
git show <source_commit>:src/ontogpt/templates/company/<company_id>/computer/v2/<company_id>_computer.yaml
```

所有来源提交都已成为 `dev-fengfeng` 的祖先，因此清理工作树和已合并本地分支后仍可按提交恢复。需要重新开展独立编辑时，应从对应来源提交创建新的工作树，不在本归档目录直接启用 Schema。

本次不部署，不写运行数据库，不调用真实模型或短信。

## 2026-11-08 后续 v2 源码整合

用户明确要求将全部候选整合为买方、供应商各一份 v2。新增的两套模板和源码注册项见 [v2 说明](../schemas/v2.md)，保留 v1；本目录原始候选及 `manifest.json` 仍描述归档时的状态，不改写为业务已审核或运行已启用。本次仍不部署、不修改运行数据库。
