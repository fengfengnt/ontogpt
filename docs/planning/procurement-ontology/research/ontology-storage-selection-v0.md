# 首版本体权威库与互操作选型依据

状态：保留当时条件下的比较记录。用户随后明确后期需要 RDF/OWL 交换和 SPARQL 查询；当前选型见[Jena 权威库决策](../issues/33-evaluate-jena-fuseki-as-authoritative-store.md)及其[复核依据](./jena-fuseki-authoritative-store-v0.md)。本文件中“待确定互操作需求”的前提已过时，不能单独作为实施选型；尚未实现或做真实负载验证。

## 已确认的试点条件

- 首版一家甲方、一家乙方；企业本体、分类树、候选、来源、不可变发布版本和判定审计由本工程管理。
- 外部系统只通过业务 JSON API/MCP 使用本工程；目前没有 RDF/OWL 文件交换、SPARQL 查询或图数据库直连的已知互操作方。
- 普通问答只扩展最多三跳、返回最多十条授权路径；没有无界图分析、形式逻辑推理需求。
- 暂无必须复用的数据库、部署限制或事实与关系的规模估计。上面的缺失是选型验证边界，不等于系统规模很小。

## 建议

**首版采用 PostgreSQL 作为唯一权威数据库。** 以结构化表保存企业、分类树、已发布定义、逐条陈述、来源修订、候选批次、发布版本与判定审计；不把整份本体仅塞进单个 JSON 文档。陈述记录保留稳定 ID、主体、关系、客体或带类型的值、范围、有效期、来源及版本。`jsonb`只承载不同业务条目的非核心扩展字段。API/MCP 负责访问控制和输出裁剪，图形化界面也通过 API 读取。

这个建议是从当前产品查询形态作出的推论：PostgreSQL 的`WITH RECURSIVE`可沿关系表做有界路径查询，并提供路径与循环处理写法；`jsonb`支持按需要索引的扩展字段；行级安全策略可作为企业隔离的数据库层防线。这些能力**不自动证明**当前数据规模下的性能或权限正确性，仍须用试点数据和越权用例验证。[PostgreSQL 递归查询](https://www.postgresql.org/docs/current/queries-with.html)、[JSONB 与索引](https://www.postgresql.org/docs/current/datatype-json.html)、[行级安全策略](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)。

| 方案 | 当前适配度 | 改选触发条件 |
| --- | --- | --- |
| PostgreSQL 权威库 | 覆盖有界关系路径、发布与审计记录、企业隔离；只运营一个数据库产品。此为当前推荐。 | 用真实试点数据和索引验证后，关键三跳查询仍达不到双方确定的延迟目标，或出现现有模型难以满足的图查询。 |
| Neo4j 权威库或读副本 | Cypher 对可变长路径有直接表达能力；若大量复杂、频繁的跨关系路径查询成为核心，可重新比较。[Neo4j 路径模式](https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-paths/)。 | 先证明上述查询需要，再设计版本、来源和授权。Neo4j 官方说明 Community Edition 只有一个标准数据库，细粒度访问控制教程适用 Enterprise Edition；多企业隔离方案和版本许可须在引入前核定。[数据库数量](https://neo4j.com/docs/operations-manual/current/database-administration/)、[细粒度访问控制](https://neo4j.com/docs/operations-manual/current/tutorial/access-control/)。 |
| RDF 三元组库 | 当确定的合作系统要求 RDF/OWL 交换、SPARQL 或标准推理时才评估。RDF 的基本图模型是主体、谓词、客体三元组；SPARQL 是针对 RDF 的查询语言。[RDF 数据模型](https://www.w3.org/TR/rdf12-concepts/)、[SPARQL 查询规范](https://www.w3.org/TR/sparql11-query/)。 | 获得具体互操作系统、需要交换的语义、格式、调用方式与验收样本；仅“将来可能需要”不足以替换首版权威库。 |

## 给实施人员的边界

1. 先设计数据库无关的陈述与关系契约：定义和实例分开；陈述可单独引用；主体/客体身份、方向、范围、有效期、明确否定、来源和版本须能回溯。发布快照不可改；本次临时声明在项目判定输入中，不能写成已发布事实。
2. PostgreSQL 实施时，关系路径查询必须先按企业与披露授权过滤，限制关系类型、方向、三跳和返回量，并防止环路；不要靠`LIMIT 10`代替遍历边界。行级安全策略可作纵深保护，但表所有者和特权角色可绕过常规策略，应用层仍须验证企业和业务授权。[递归查询与循环处理](https://www.postgresql.org/docs/current/queries-with.html)、[行级安全注意事项](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)。
3. 真实规模未知，首批样本到位后测量分类树读取、三跳问答、候选确认与整批发布、并发跨企业访问；记录数据量、查询计划和延迟，再决定是否添加专用检索索引或图读副本。不得把当前选型表述为已完成性能验收。
4. 首版不交付 RDF/OWL 导出或 SPARQL 端点。保留稳定 ID、类型和谓词含义，是将来建立映射的准备，不代表未来导出可零成本完成。
