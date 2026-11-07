# 界定首版本体事实与关系的权威表示

Type: grilling
Status: resolved

## Related

- [界定企业资料到本体候选的采集与确认流程](./04-define-company-knowledge-intake.md)
- [界定首次企业资料投喂到本体候选的最小契约](./25-define-initial-ontology-ingestion-contract.md)
- [界定通用本体问答的结论与证据边界](./29-define-ontology-answer-evidence-contract.md)
- [乙方能力、事实与本次声明结构](../ontology/supplier-model-v0.md)

## Question

为使已发布企业本体可以被检索、给出真实关系路径并追溯来源，首版以什么作为可单独确认、版本化和引用的事实单位？是否要求形式逻辑推理或 RDF/OWL 互操作作为首版对外契约？

## Established boundary

- 首次投喂用`Class / Property / Relation / Constraint / Instance`五种通用承载结构生成候选，定义与实例分开；三级品类树单独版本化。
- 已发布知识包条目、乙方能力与事实均有稳定 ID、来源、适用范围和版本；本次声明不自动改写已发布事实。
- 通用问答须返回实际路径，并可区分支持、反驳、依据不足和冲突；采购条件由 LLM 按发布规则与本次输入判断。
- 本工程对外提供业务 API 与少量 MCP Tools；此前规格未锁定数据库、RDF 或 OWL 表示。

## 用于检验选择的例子

乙方的已发布资料写“华硕笔记本提供三年维保，仅上海地区”；后来该乙方在采购项目 P 中声明“五年维保”。需要分别引用旧事实与本次声明，显示时间、地域、来源和冲突，而不能只存一个会被覆盖的`维保年限`字段。

## Decision

- 已发布事实和关系均以可单独引用的陈述记录为权威单位，至少保留主体、关系、客体或值、适用范围、有效期、来源片段及发布版本；图上可投影成节点与连线。旧事实与本次声明各有独立引用，本次声明不能覆盖已发布陈述。
- 首版沿明确发布的关系和来源进行有界检索，业务含义及条件满足由 LLM 按已发布知识包与本次输入判断；不承诺 OWL 等形式逻辑引擎自动推出未写出的事实。
- 首版对外固定业务 JSON API 和 MCP Tools。2026-10-16 用户进一步明确**后期肯定需要 RDF/OWL 交换和 SPARQL 查询**；长期存储选型已由[Jena 复核决策](./33-evaluate-jena-fuseki-as-authoritative-store.md)修订为 TDB2 本体权威库。此前[PostgreSQL 原选型依据](../research/ontology-storage-selection-v0.md)保留为当时条件下的分析记录。
- 真实数据量下的性能、隔离及 RDF/OWL 往返仍未验证；不能保证选定数据库后永不迁移。
