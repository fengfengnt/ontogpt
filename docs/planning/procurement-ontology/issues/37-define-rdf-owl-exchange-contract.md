# 界定 RDF/OWL 文件交换契约

Type: grilling
Status: out-of-scope

## Related

- [评估 Jena Fuseki/TDB2 作为本体权威库](./33-evaluate-jena-fuseki-as-authoritative-store.md)
- [界定带范围事实的 RDF 陈述与来源模型](./35-define-rdf-claim-and-provenance-model.md)
- [界定 RDF 词汇与 SHACL 校验边界](./36-define-rdf-vocabulary-and-shacl-boundary.md)

## Question

后期向其他系统导出或从其导入 RDF/OWL 时，明确支持哪些文件格式和内容范围？如何保留企业隔离、词汇 IRI、带范围陈述、来源权限和版本，并使外部导入仍经过候选、人工确认和发布，而不把文件直接写入当前已发布图？

## Scope decision

用户明确要求当前先实现提供企业本体数据的基础功能，RDF/OWL 文件交换留到项目后期。因此本票退出当前决策地图；保留问题供后续单独规划，不作为首版交付或当前实施的前置条件。内部采用 TDB2/RDF 的已定存储方案不等于首版必须提供 RDF/OWL 文件交换接口。
