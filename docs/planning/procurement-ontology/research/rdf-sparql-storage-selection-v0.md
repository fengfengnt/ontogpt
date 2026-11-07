# RDF/OWL 与 SPARQL 长期存储选型依据

状态：保留 2026-10-16 PostgreSQL + Ontop 的比较记录；首选结论已由[评估 Jena Fuseki/TDB2 作为本体权威库](../issues/33-evaluate-jena-fuseki-as-authoritative-store.md)修订，当前选型见[Jena 复核依据](./jena-fuseki-authoritative-store-v0.md)。本文件不表示已实现或通过试点验证。

## 已确认的要求

- 首版一家甲方、一家乙方，业务 JSON API/MCP；后期确定需要 RDF/OWL 标准文件交换和授权系统只读 SPARQL，不要求首期 OWL 自动推理。
- 免费、开源、自托管；企业本体候选必须经确认和发布，历史发布快照可追溯；跨企业资料受授权和披露范围限制。
- 目前没有明确的外部 SPARQL 查询语句、OWL 构造范围、数据规模或性能目标。因此可以定权威库，不能声称任意查询与无损文件往返已被验证。

## 选型

| 组件 | 决定 | 理由与边界 |
| --- | --- | --- |
| PostgreSQL | 首版唯一权威数据库 | 企业、版本、候选、来源、陈述和审计均需事务性管理；其关系表可做有界递归查询，JSONB 可承载非核心扩展，RLS 可作隔离的辅助防线。[递归查询](https://www.postgresql.org/docs/current/queries-with.html)、[JSONB](https://www.postgresql.org/docs/current/datatype-json.html)、[RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)。 |
| Ontop | 后期首选只读 SPARQL 适配层 | 以 R2RML 把关系数据虚拟映射为 RDF、SPARQL 翻译成 SQL；不要求再维护一份事实库。官方明确只支持 SPARQL 1.1 的大部分功能，任意长度属性路径及 `SERVICE` 等不支持。[原理](https://ontop-vkg.org/guide/concepts.html)、[兼容矩阵](https://ontop-vkg.org/guide/compliance.html)、[Apache 2.0 许可](https://github.com/ontop/ontop)。 |
| Apache Jena Fuseki/TDB2 | 仅在实际查询超出 Ontop 支持范围时作为只读发布投影 | Fuseki 提供 SPARQL 1.1 查询服务器及 TDB 持久层；引入后要承担发布同步和两个数据副本的一致性检查。它不是首版权威库。[Fuseki](https://jena.apache.org/documentation/fuseki2/)、[访问控制](https://jena.apache.org/documentation/fuseki2/fuseki-data-access-control.html)。 |
| Neo4j Community | 可行的图权威库备选，当前不选 | 节点与关系、Cypher 路径查询适合图探索；n10s 可交换 RDF/OWL，但 OWL 专用导入器只接收一部分构造，不能等同于完整 OWL 或原生 SPARQL 服务。Community 仅有一个标准数据库，细粒度图权限属于 Enterprise；多企业隔离需由本工程另行实现和验证。若试点证实复杂路径查询是主要负载，才重新比较此方案。[Cypher](https://neo4j.com/docs/cypher-manual/current/introduction/)、[n10s](https://neo4j.com/labs/neosemantics/)、[OWL 导入边界](https://neo4j.com/labs/neosemantics/4.3/importing-ontologies/)、[数据库数量](https://neo4j.com/docs/operations-manual/current/database-administration/)、[权限版本](https://neo4j.com/docs/operations-manual/current/tutorial/access-control/)。 |

这是一项从当前产品边界作出的**架构推论**。选择 PostgreSQL 并不排斥 RDF 标准：RDF 是交换和查询视图，权威事实仍可由关系库保存。Ontop 官方说明数据留在原关系库中，并由映射生成虚拟 RDF 图。[Ontop 核心概念](https://ontop-vkg.org/guide/concepts.html)。

## 文件交换与访问边界

1. 从首版起给类、属性、关系、实例和逐条陈述稳定 ID，并定义稳定 IRI 映射；保存对象与字面量类型、语言、范围、有效期、来源片段和发布版本。业务规则、流程与显式否定需自定义词表或附加文档，不能直接假定 OWL 能无损表达全部业务语义。
2. 后期导出已发布且获授权的 RDF/OWL 文件；Ontop 的 `materialize` 可把映射数据输出为 Turtle、N-Triples、RDF/XML 等，但本体定义和业务扩展仍需本工程的受控导出逻辑。[Ontop materialize](https://ontop-vkg.org/guide/cli)。导入文件先生成带来源的候选，逐项确认并发布；不开放 SPARQL Update 绕过治理。OWL 2 的标准交换语法包括 RDF/XML，也可使用 Turtle；文件交换与推理是两项不同能力。[W3C OWL 2 概览](https://www.w3.org/TR/owl-overview/)。
3. Ontop 端点不直接公开；授权系统经本工程鉴权，绑定企业和只读数据库视图/账号。不得让跨企业项目临时披露进入通用 SPARQL 视图。具体租户隔离配置需在首个 SPARQL 接入前用越权查询验证。
4. 用真实合作方的查询与文件做验收：至少覆盖同一陈述的 API、RDF 导出与 SPARQL 查询一致性；来源/版本和租户隔离；已支持子集的导入→确认→导出往返；Ontop 不支持的查询清单。若需要 Jena 投影，另测发布同步与旧版查询。

## Palantir 给出的参照

Palantir 官方把 Ontology 描述为连接对象、关系、数据、逻辑、动作和安全的企业运行层，而不是“选择一种三元组数据库”的同义词。[Ontology 系统架构](https://www.palantir.com/docs/foundry/architecture-center/ontology-system)、[Ontology 概览](https://www.palantir.com/docs/foundry/ontology/overview)。其当前 Ontology Manager 文档说明本体 schema 工作状态可按 JSON 导入/导出；2022 年互操作白皮书提到 RDF/OWL 格式，但不能据此推断其现行所有交换能力、SPARQL 服务或底层存储产品。[当前导入导出文档](https://www.palantir.com/docs/foundry/ontology-manager/export-import)、[2022 互操作白皮书](https://www.palantir.com/assets/xrfr7uokpv1b/7BxLPkTqJU9QhLTQCjJMo6/eed1457949dc2d1cd6b6e71936c0aa9c/Enabling_Interoperability_and_Embracing_Openness_with_Foundry.pdf)。
