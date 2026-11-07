# 带范围事实的 RDF 陈述与来源（设计稿）

状态：数据表示规格，尚未实现。决策见[带范围事实与来源票据](../issues/35-define-rdf-claim-and-provenance-model.md)。下文 `ex:` IRI 仅为示例，不是已冻结的产品词汇。

## 权威单位

已发布的业务事实、否定事实与关系各有稳定陈述 IRI。它记录主体、谓词、客体或带类型的值、肯定/否定、适用品类/品牌/地域/项目等范围、有效期，并关联一条或多条**独立的来源片段引用**；人工图上修订也作为独立来源记录。类和分类树的无条件结构关系可直接用普通 RDF 三元组；带范围的业务事实只通过陈述资源发布。

示例：乙方 A 声称“上海地区华硕笔记本提供三年维保”。两份资料分别支持相同含义：

```turtle
@prefix ex: <https://example.org/procurement/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:claim-001 a rdf:Statement ;
    rdf:subject ex:supplier-A ;
    rdf:predicate ex:providesWarrantyYears ;
    rdf:object "3"^^xsd:integer ;
    ex:polarity ex:Affirmed ;
    ex:appliesToBrand ex:Asus ;
    ex:appliesToCategory ex:Notebook ;
    ex:appliesToRegion ex:Shanghai ;
    ex:validFrom "2026-01-01"^^xsd:date ;
    ex:validUntil "2026-12-31"^^xsd:date ;
    prov:wasDerivedFrom ex:excerpt-101, ex:excerpt-205 .
```

`ex:excerpt-101`和`ex:excerpt-205`是不同的来源片段实体，各自记录文档/对话 ID、文件版本或消息时间、原文片段与位置；原文与来源元数据按企业及采购披露权限读取。`prov:wasDerivedFrom`表示陈述由来源片段得到，不表示来源文件本身已被外部系统核验。发布版本图保存当时的陈述及来源引用；片段实体不可被后续文档修订原地改写。

**不要再写**`ex:supplier-A ex:providesWarrantyYears 3`作为同一业务事实：这条直接三元组没有上海、华硕笔记本和有效期限定。按 [W3C RDF 语义](https://www.w3.org/TR/rdf11-mt/#reification)，`rdf:Statement` 的重述本身也不蕴涵这条直接三元组。[PROV-O](https://www.w3.org/TR/prov-o/)定义了来源关系；本产品的品牌、地域和有效期含义仍需由自身词汇与判定规则解释。

## 身份、版本和读取

- 只有主体、谓词、值、极性、适用范围、有效期**全部等价**的两段内容才合并为同一陈述，并各留来源；同名、文本相似或同属“维保”不足以合并。不同条件仍各有 IRI，冲突检查按范围与时间比较。
- 一条陈述在多个不可改发布快照中可沿用同一 IRI。新增相同事实的来源时，新快照增加来源引用，旧快照仍保持原样；语义字段变更时建立新陈述并按替代/终止规则处理旧陈述。
- 普通 Agent 只读当前发布快照。`get_ontology_item`按陈述 ID 返回限定范围和获授权的来源，一跳业务关系按**逻辑陈述**计一跳，不把 `rdf:subject / rdf:predicate / rdf:object` 三个存储字段当成三跳。历史判定通过审计引用回看原快照。
- 后期只读 SPARQL 应查询获授权的当前图中的陈述资源，并按范围及时间过滤；来源片段在受限图中按权限补取。一个只查`?s ?p ?o`直接三元组的通用 SPARQL 客户端不会读到这些带范围业务事实，互操作文档必须附查询范式。RDF/OWL 导出保留陈述、限定字段和来源引用，不把它们展开成无条件断言。

示意查询（图 IRI 也仅为示例）：

```sparql
PREFIX ex: <https://example.org/procurement/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?claim ?years WHERE {
  GRAPH <https://example.org/company/A/current/ontology> {
    ?claim a rdf:Statement ;
      rdf:subject ex:supplier-A ;
      rdf:predicate ex:providesWarrantyYears ;
      rdf:object ?years ;
      ex:polarity ex:Affirmed ;
      ex:appliesToBrand ex:Asus ;
      ex:appliesToCategory ex:Notebook ;
      ex:appliesToRegion ex:Shanghai ;
      ex:validFrom ?from ; ex:validUntil ?until .
    FILTER (?from <= "2026-06-01"^^xsd:date && ?until >= "2026-06-01"^^xsd:date)
  }
}
```

此查询只证明在给定范围与日期找到了相应陈述。是否满足一次采购的五年维保条件，仍由本工程结合甲方知识包、本次输入和乙方临时声明作专用判定。

## 最小验证样例

1. 两份完全同义同范围的原文得到一条陈述、两条来源，删去或替换来源不会改写历史快照。
2. “上海三年”不命中北京查询；过期事实不命中当前日期；华硕公司的注册资本不被误归到供应商 A。
3. 项目 P 的“五年维保”临时声明不进入当前已发布图；本次判定可同时引用它和旧的三年陈述并按已定诚信规则显示冲突。
