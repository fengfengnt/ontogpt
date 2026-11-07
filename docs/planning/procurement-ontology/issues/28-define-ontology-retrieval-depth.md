# 界定本体关联读取深度与首版问答检索

Type: domain-modeling
Status: resolved

## Related

- [界定 Agent 读取已发布企业本体的最小契约](./27-define-agent-ontology-read-contract.md)
- [Agent 本体读取接口设计稿](../api/ontology-read-v0.md)
- [二级品类知识包结构设计稿](../ontology/knowledge-pack-v0.md)

## Question

按本体条目 ID 读取时应自动展开几层关联？首版通用问答检索如何在不把整张图交给 Agent 的情况下，找到足以回答问题的关联事实并保留可审计路径？

## Answer

- 图查询语言没有统一的业务默认层数，可表达固定或可变长度路径；无边界的广泛遍历会扩大结果与成本。首版将**导航**和**问答上下文检索**区分：`get_ontology_item(id)`返回本条目详情及直接相邻关系的类型、方向、目标 ID/简述，即一跳关系摘要，不递归装入目标的全部事实。
- `search_ontology_items(question)`先找相关条目作为起点，再依据问题相关性和**有类型、有方向**的关系逐层扩展；首版最多三跳、最多返回十条相关路径。三跳和十条是本产品的初始上限，不是业界标准，试点案例可检验是否漏答或引入噪声。每条返回路径包含实际节点与关系 ID、类型、适用范围、来源片段和所用版本。关系必须真实存在，不能由 LLM 编造。
- 检索只走调用方有权看到、当前已发布且在查询时间适用的内容；先做企业与披露权限过滤，再扩展。普通搜索仍只看最新版；在办判定按绑定快照内部运行。若上限内没有足够依据，返回“未找到足够依据”，而非把高相关或远处节点强行当答案。
- 准入、硬约束与流程等业务问题仍由专用`analyze_procurement_draft`、`evaluate_supplier_admission`等操作按规则判断。通用检索只给可解释上下文，不能把“路径可达”当作“条件满足”。
- 例如“品牌范围 → 华硕 → 华硕公司 → 注册资本”是三跳路径，但如果问题问**供应商**注册资本，这条路径的最后一项属于品牌所属公司，不能充作供应商资本。关系的主体、方向与业务角色比层数更决定答案是否正确。

## 依据与限制

- [W3C SPARQL 1.1 Property Paths](https://www.w3.org/TR/sparql11-query/#propertypaths)支持固定及任意长度路径，没有规定知识库默认展开层数。
- [Neo4j Variable-length paths](https://neo4j.com/docs/cypher-manual/current/patterns/variable-length-paths/)说明可变长路径在宽泛模式下会产生大量路径，建议设置上限或过滤节点与关系。
- [Microsoft GraphRAG Local Search](https://microsoft.github.io/graphrag/query/local_search/)从与问题相关的实体出发，选取关联实体、关系和来源文本，再按上下文预算排序过滤。

本票定义产品读取行为，不选择图数据库，也不声称三跳可覆盖所有问题；首版必须用采购与供应案例记录漏答、误关联和返回路径。
