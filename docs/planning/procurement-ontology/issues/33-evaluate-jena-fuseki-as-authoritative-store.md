# 评估 Jena Fuseki/TDB2 作为本体权威库

Type: research
Status: resolved

## Related

- [原长期存储架构决策](./32-define-rdf-sparql-storage-architecture.md)
- [Jena 选型复核](../research/jena-fuseki-authoritative-store-v0.md)

## Question

既然后期 RDF/OWL 文件交换和授权只读 SPARQL 是确定要求，Apache Jena Fuseki/TDB2 能否直接承载企业本体、候选、版本和审计，减少未来转换与搬迁？

## Decision

- **将 Apache Jena TDB2 定为本体工程首选权威存储，Fuseki 作为访问服务**；取代前票的 PostgreSQL 权威库加 Ontop 首选方案。首版仍只向外部 Agent 开放业务 JSON API/MCP，不直接开放任意 SPARQL 写入。
- 用 RDF 命名图区分企业、通用基线、分类树、候选批次和已发布快照；以稳定 IRI 标识类、属性、关系、实例及可单独引用的事实陈述。候选确认、冲突校验、不可变发布和当前版本切换由本工程实现，不能以“使用 RDF 库”代替这些业务治理能力。
- 授权系统的后期 SPARQL 仅开放只读、按企业与披露范围过滤的视图；内部发布服务才可写入。Fuseki 的图级 ACL 适用于只读数据集，跨企业按采购项目逐项披露仍走业务 API，不把私有材料直接暴露给通用 SPARQL 端点。
- RDF/OWL 文件导入先生成候选并人工确认；导出只包含已发布且获授权的数据。OWL 的交换、存储和推理分别定义，首版不承诺完整 OWL 自动推理或任意外部 OWL 文件的业务语义无损导入。
- 当前决定是基于官方功能文档和已知产品要求的设计判断；未做真实负载、租户越权、批次发布或 RDF/OWL 往返实测。若实际试点显示治理写入或文本审计不适合单一 TDB2，再增加业务元数据库，不更换本体权威格式和存储。
