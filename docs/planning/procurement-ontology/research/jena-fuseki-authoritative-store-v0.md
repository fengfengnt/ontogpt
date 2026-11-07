# Apache Jena Fuseki/TDB2 权威库选型复核

状态：2026-10-16 设计决策依据；尚未部署或完成试点验证。此前[PostgreSQL + Ontop 方案](./rdf-sparql-storage-selection-v0.md)保留为比较记录，当前选型以[复核决策](../issues/33-evaluate-jena-fuseki-as-authoritative-store.md)为准。

## 为什么改选

用户已确定后期要 RDF/OWL 标准文件交换和授权只读 SPARQL。Fuseki 是 SPARQL 服务端，TDB2 是持久化 RDF 存储；TDB2 有事务，支持命名图，Jena 可读写 RDF 文件并提供 SHACL 验证。[Fuseki](https://jena.apache.org/documentation/fuseki2/)、[TDB2](https://jena.apache.org/documentation/tdb2/index.html)、[事务](https://jena.apache.org/documentation/tdb/tdb_transactions.html)、[命名图](https://jena.apache.org/documentation/tdb/datasets.html)、[SHACL](https://jena.apache.org/documentation/shacl/index.html)。两者采用 Apache License 2.0，满足免费开源、自托管要求。[许可](https://jena.apache.org/documentation/fuseki2/)。

此前 PostgreSQL + Ontop 方案的优势是业务记录管理熟悉且只维护一个关系库；但 Ontop 官方只支持 SPARQL 1.1 的大部分功能，任意长度属性路径及联邦查询等不支持。既然标准 SPARQL 是确定目标，本体事实先存 TDB2 可少一层长期映射限制。[Ontop 兼容矩阵](https://ontop-vkg.org/guide/compliance.html)。这是一项针对本产品要求的架构推论，并非 TDB2 已通过本产品负载验收。

## 最小架构

1. TDB2 存放企业和平台本体定义、分类树、逐条事实陈述、知识包、来源引用、候选与发布审计。用命名图区分企业与发布版本；候选图区分批次。每条需审计的陈述另有稳定 IRI 和来源、范围、有效期等元数据。已发布图由应用保持不可改，当前版本指针由应用受控切换。TDB2 事务提供原子写入基础，但不自动实现上述业务规则。[TDB2 事务](https://jena.apache.org/documentation/tdb/tdb_transactions.html)。
2. 首版应用服务是唯一写入者，对外只提供既定 JSON API/MCP。后期授权系统经独立只读 Fuseki 端点查询已发布图；Fuseki 可配置服务、数据集、端点及图级 ACL。图级 ACL 当前只适用于只读数据集，不能拿它直接实现采购项目的逐项证据披露。[Fuseki 访问控制](https://jena.apache.org/documentation/fuseki2/fuseki-data-access-control.html)。
3. Jena 解析 RDF/OWL 文件后仍生成候选，不自动变成事实；导出从获授权的已发布图生成。OWL 文件交换与完整 OWL 推理分开：Jena 自带的 OWL 规则推理器并不完整，而首版也没有自动推理要求。[RDF 读取](https://jena.apache.org/documentation/io/rdf-input.html)、[OWL 推理范围](https://jena.apache.org/documentation/inference/index.html)。

## 与其他选择的边界

| 方案 | 当前判断 |
| --- | --- |
| Jena Fuseki + TDB2 作本体权威库 | 优先选用；标准 RDF/SPARQL 能力直接对应后期要求，单一权威本体数据源。候选、审批、版本和来源治理仍由产品实现。 |
| PostgreSQL + Ontop | 可行备选；关系型治理便利，但后期 SPARQL 能力受 Ontop 支持范围约束，RDF/OWL 需要映射和导入流程。 |
| PostgreSQL + Jena 只读投影 | 两类数据各有适合的存储，但需处理发布同步及跨库一致性；仅当试点证明 TDB2 单库存储业务治理记录不合适时采用。 |
| Neo4j Community + n10s | 图路径方便，但 Cypher 是主要查询语言；n10s 的 OWL 专用导入只覆盖一部分构造，不能直接充当完整 SPARQL 服务。免费版多企业隔离边界另需设计。[Neo4j n10s](https://neo4j.com/labs/neosemantics/)、[OWL 导入范围](https://neo4j.com/labs/neosemantics/4.3/importing-ontologies/)。 |

## 首批验证

- 用试点甲乙方样本分别存入候选图、确认发布到版本图，验证旧版可追溯、同批发布原子性和冲突处理。
- 以两个企业和一份只对本次采购披露的证据做越权查询，验证 API/MCP 与只读 SPARQL 的可见范围。
- 用一组真实 RDF/OWL 文件及查询验证“导入为候选 → 确认发布 → SPARQL 读取 → 授权导出”的往返，以及未覆盖构造的报告。
- 测量三跳路径、知识包查询和发布事务的时延与存储量；根据结果决定是否需要独立的业务元数据库。
