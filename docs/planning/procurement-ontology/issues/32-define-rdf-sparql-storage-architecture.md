# 界定兼容 RDF/OWL 与 SPARQL 的长期存储架构

Type: grilling
Status: resolved

后续修订：本票的 PostgreSQL + Ontop 首选结论已由[评估 Jena Fuseki/TDB2 作为本体权威库](./33-evaluate-jena-fuseki-as-authoritative-store.md)取代；保留本票作为决策历史。

## Related

- [界定首版本体事实与关系的权威表示](./31-define-authoritative-ontology-fact-model.md)
- [首版原选型依据](../research/ontology-storage-selection-v0.md)
- [RDF/OWL 与 SPARQL 长期选型依据](../research/rdf-sparql-storage-selection-v0.md)

## Question

既然后期确定要支持 RDF/OWL 交换和 SPARQL 查询，首版应怎样选定权威存储与 RDF 查询层，尽量避免未来替换或搬迁？Palantir 的企业 Ontology 架构能借鉴什么，不能由它推断什么？

## Established boundary

- 已确认事实与关系逐条可引用，保留来源、范围、有效期和发布版本；首版外部 Agent 使用业务 JSON API/MCP。
- 用户明确后期肯定需要 RDF/OWL 交换与 SPARQL；此前“没有已知试点互操作方”只表示当前试点不直接接入这些协议，不能否定后期要求。
- 试点暂无指定数据库或规模限制。用户要求免费、开源、自托管；后期先做 RDF/OWL 标准文件交换与授权系统只读 SPARQL，不要求 OWL 自动推理。

## Decision

- **PostgreSQL 定为唯一权威数据库**，从首版保存企业本体定义、逐条陈述、分类树、候选、来源、版本和判定审计。陈述保留稳定身份及可映射到 RDF IRI/字面量的类型信息；业务 API/MCP 读取本体时使用获授权的已发布版本，准入判定另可接收本次临时输入。
- **Ontop 定为后期首选的只读 RDF/SPARQL 适配层**：用 R2RML 将 PostgreSQL 中已发布且可披露的内容映射为虚拟 RDF 图，不另存一份权威事实。SPARQL 经本工程鉴权并绑定企业范围；数据库账号只读。跨企业按项目临时披露的数据仍走业务 API，不进入普通企业 SPARQL 图。
- RDF/OWL 文件**导出**按已发布版本和授权范围生成；文件**导入**先解析成待确认候选，再走人工确认与批次发布，不能直接写权威库。先定义并验证受支持的交换子集；企业业务规则及工作流不能假定由 OWL 原生、无损表达。
- Ontop 只支持 SPARQL 1.1 的大部分功能，不能承诺任意 SPARQL 查询都可运行，特别是部分任意长度属性路径与联邦查询。拿到互操作方的实际查询后做兼容验收；若确需完整相关查询能力，增加 Apache Jena Fuseki/TDB2 作为**已发布数据的只读投影**，仍不替换 PostgreSQL 权威库。
- 不承诺数据库永不更换：当前需求下可锁定权威库和迁移边界；真实数据量、隔离方式与 RDF/OWL 往返尚未实测。Palantir 可借鉴的是对象/关系、逻辑、动作、安全分层，不足以推断其底层库或把 RDF 库视为必要条件。
