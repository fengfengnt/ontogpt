# 采购方与供应商本体产品决策地图

## Destination

形成可实施的产品与本体规格：分别为采购企业和供应商企业建立本体库，通过本工程的 API/MCP 向外部采购 Agent、供应商 Agent 及其业务系统提供品类识别、按品类所需数据与流程查询、供应能力和准入条件判定及可审计依据；外部系统负责对话编排、采购发布、供应商响应和入围记录。

## Notes

- 完整产品以“采购员输入‘我要采购 100 个电脑’→本工程返回品类、待补数据和适用流程→采购 Agent 补问并由外部系统发布→供应商 Agent 从外部系统获得需求并调用本工程判定→外部系统记录邀请入围”为端到端检验场景；该场景在第二阶段验证。供应商可提供多个采购负责类和品类的服务或物料。
- 本工程对外只提供查询和判定，不创建或发布采购需求，不记录正式入围；内部从经确认的新条件及乙方新声明自动生成待确认本体候选，再由各企业审核发布。第 15 项界定按品类采集字段、逐轮校验与流程查询；第 21 项细化资格预审判定接口及诚信声明边界。
- 首版先落地一家甲方和一家乙方；平台通用基线随后从企业实践中提炼，用于后续企业。
- [第一阶段](./phase1-data-service-v0.md)先交付企业本体数据的录入、确认、发布及供 Agent 授权查询；第二阶段再交付跨企业品类匹配、逐条件判断和入围建议。RDF/OWL 文件交换及授权只读 SPARQL 留待后期。
- “行业”留待另行定义，不等同于三级分类树的顶层“采购负责类”。
- 通用本体是可版本化基线，企业可扩展；企业扩展不因基线更新而自动覆盖。
- 企业资料中的共性先脱敏为候选，经人工审核后才可发布为通用内容。
- OntoGPT 仅作为候选概念和关系的提取组件候选；是否适合首轮自由文本生成基础业务本体仍需验证，产品架构不限定在本仓库。
- 每张票据只解决一个决策。讨论时同时使用 `grilling` 和 `domain-modeling`，用具体甲乙方案例检验术语边界。
- 决策完成后再整理规格；本地图阶段不编写产品代码。
- 已完成的决策汇总为[采购企业与供应商企业本体服务：产品与本体规格](./product-spec.md)，可作为试点与实现的交接文档；尚需真实甲乙企业资料验证。

## Decisions so far

- [界定采购负责类、品类、服务能力与甲乙方本体边界](./issues/02-define-domain-vocabulary.md)：三级唯一父节点分类树；乙方能力独立于品类并决定其采购负责类归属；甲乙方共享核心语义、各有企业视图。
- [界定首版采购需求与供应商能力的业务契约](./issues/01-define-matching-business-contract.md)：条件按每次拆分采购项定义；邀请投标前核对品类覆盖和必须项；权重用于后续评分，单供应商须覆盖全部采购项。
- [界定采购职能、职责与工作流程的建模范围](./issues/03-define-procurement-roles-workflows.md)：职位、任职和上级关系由企业定义；审批按职位执行并记录操作人；业务权限与菜单权限分开，在办采购沿用原流程版本。
- [界定企业资料到本体候选的采集与确认流程](./issues/04-define-company-knowledge-intake.md)：先由自然语言生成基础业务本体候选，再按已确认 schema 提取；企业管理员确认，保留原文证据；图上编辑保存即确认修订，发布后才供新事项使用。
- [界定通用基线与企业扩展的版本关系](./issues/05-define-shared-baseline.md)：先落地一家甲方和一家乙方，再总结通用基线；企业可有本地定义和实例，固定引用基线版本并主动升级。
- [界定企业共性提升为通用本体的规则](./issues/06-define-common-knowledge-promotion.md)：两家试点经审核形成首版基线；后续同类业务三家独立企业的已确认相似内容进入审核，平台管理员脱敏后发布新版本。
- [界定可解释匹配的判定与结果](./issues/07-define-explainable-matching.md)：品类覆盖与具体条件分别判定，逐项展示依据；主观项和乙方声明的首版处理边界由后续第 21 项调整。
- [界定分类树的来源与维护责任](./issues/08-define-taxonomy-source.md)：平台自建版本化模板，甲乙方各有可修改的企业树；企业本地树独立批次发布，跨企业按完整路径和描述自动匹配，历史记录保留原版本。
- [界定通用基线升级的影响评估与迁移](./issues/09-define-baseline-upgrade.md)：业务基线与分类模板分别升级；先预览差异、逐项解决冲突，企业管理员确认后新事项才使用新版，在办及历史沿用旧版。
- [界定评标权重与分数汇总](./issues/10-define-scoring.md)：每采购项满分 100，必须项可设分数门槛；客观项可机器给入围初评分，投标最终评分及供应商选定仍按甲方流程。
- [界定跨企业品类语义匹配的判定与验收](./issues/11-define-category-semantic-matching.md)：相似度与 LLM 两步三态判断；高阈值等价结果可参与预授权自动入围，但试运行只有同一 LLM 自一致性、无独立误匹配率验收。
- [界定 Agent 访问企业本体与匹配结果的接口](./issues/12-define-agent-ontology-interface.md)：版本化 API 加少量 MCP Tools，按用户或限定服务身份授权；支持品类字段与流程查询、外部传入数据后的判定，不承接采购或入围写入。
- [界定企业本体版本的确认与发布](./issues/13-define-enterprise-ontology-publication.md)：每企业单一待发布批次，候选逐项采纳或拒绝；图上保存进入批次，校验后管理员整批发布不可改快照；分类树单独发布。
- [界定本体工程与外部 Agent 的业务边界](./issues/14-define-ontology-service-agent-boundary.md)：本工程分别服务甲乙方本体，返回品类所需字段、流程、能力与条件判定；外部系统负责对话、采购发布、响应和人工或预授权自动入围记录。
- [界定一句话采购需求到正式发布的业务契约](./issues/15-define-conversational-procurement-publication.md)：品类歧义请采购员选择；品类关联需求字段与供应条件模板，外部保存草案；每轮按最新本体校验并返回缺失、无效、流程与数据齐备状态。
- [界定供应商 Agent 接收需求到邀请入围的业务契约](./issues/16-define-supplier-agent-shortlist-flow.md)：乙方可独立自检并与甲方 Agent 澄清；甲方预授权后外部系统可自动邀请，判定与正式状态分离；诚信声明的判定由第 21 项细化。
- [界定二级品类知识包与案例验收](./issues/17-define-category-knowledge-pack-and-case-review.md)：品类只筛候选，知识包组织需求、条件、证据及判定规则；案例先写人工预期再复核，误入围案例修正重测后方可启用该品类自动入围。
- [界定笔记本案例可用于知识包与入围验收的范围](./issues/18-assess-laptop-case-as-ontology-input.md)：模拟案例用于知识包建模；本次入围预期为资格预审的 8 通过、3 不通过，后续废标属评标阶段；缺原始乙方证据及若干规则澄清。
- [明确模拟笔记本案例的资格预审规则](./issues/19-resolve-laptop-prequalification-rule-conflicts.md)：经营范围补为本次模拟采购的明示资格必须项；9,500 元为价格目标，30 天交期为投标评分项，均不否决预审。
- [界定资格预审判定的乙方事实与证据输入](./issues/20-define-prequalification-evidence-input.md)：可复用乙方事实归已发布本体，项目专属材料可随请求传入，原件留外部；无原件的诚信声明处理由第 21 项补充。
- [界定资格预审判定 API 的最小契约](./issues/21-define-prequalification-api-contract.md)：原话与确认快照共同校验；逐条件诚信声明可参与自动判断，冲突标记但本次声明优先；新条件/新声明由本工程自动去重入待确认候选，正式入围仍由外部系统记录。
- [界定二级品类知识包的可执行本体结构](./issues/22-define-knowledge-pack-structure.md)：知识包分条建模；企业硬约束作为本体规则按范围生效；全部业务条件由 LLM 判，程序做基础校验，普通上级规则不隐式继承。
- [界定采购对话草案校验与流程查询 API 的最小契约](./issues/23-define-procurement-draft-api-contract.md)：原话可定位的新要求直接入本次草案，LLM 额外推荐只供选择；缺知识包时临时建议逐项确认，整份快照确认后新知识入候选，流程不明补问并在发布前按最新版复核。
- [界定乙方能力、事实与本次声明的本体结构](./issues/24-define-supplier-ontology-structure.md)：乙方能力与可复用事实分开、按范围和有效期关联；项目临时能力可用临时三级路径匹配并入候选；可复用承诺发布后默认通用，项目明示限制保留；新能力发布时明确确认是否进入常规检索。
- [界定首次企业资料投喂到本体候选的最小契约](./issues/25-define-initial-ontology-ingestion-contract.md)：无业务 schema 时用五种通用结构承载提议，逐项保留原文；资料改版生成带拟替代关系的候选，缺原文依据的模型推断只列建议，不进入事实候选。
- [界定候选依赖、规则替代与分类树发布顺序](./issues/26-define-candidate-dependencies-and-publication-order.md)：业务本体批次发布前验证依赖闭包；新分类节点先于引用它的知识包/能力发布；拟替代旧规则时人工确认旧终止、新开始时间，旧快照不改。
- [界定 Agent 读取已发布企业本体的最小契约](./issues/27-define-agent-ontology-read-contract.md)：普通 Agent 先搜索再按 ID 读取，仅读最新版且只返授权来源片段；在办判定沿绑定旧快照，历史通过具体审计引用解释，不开放任意旧版搜索。
- [界定本体关联读取深度与首版问答检索](./issues/28-define-ontology-retrieval-depth.md)：按 ID 读取只给一跳关系摘要；问答搜索从相关条目出发，按关系类型与问题相关性最多扩展三跳、返回最多十条可追溯路径；路径可达不等于业务条件满足。
- [界定通用本体问答的结论与证据边界](./issues/29-define-ontology-answer-evidence-contract.md)：搜索只找候选；明确命题另由只读接口返回支持、反驳、依据不足或冲突及真实证据路径；缺失不等于否定，项目声明仅进入专用准入判定。
- [界定自然语言问句到可核验本体命题的转换](./issues/30-define-natural-language-claim-grounding.md)：核验可直接接收自然语言并识别主体；主体、关系或门槛不明则返回不足与缺失信息；缺少本次采购条件时如实回答查不到，不规定 Agent 后续动作。
- [界定首版本体事实与关系的权威表示](./issues/31-define-authoritative-ontology-fact-model.md)：事实和关系逐条可引用，首版 Agent 接口用 JSON API/MCP；后期互操作选型另见下一决策。
- [界定兼容 RDF/OWL 与 SPARQL 的长期存储架构](./issues/32-define-rdf-sparql-storage-architecture.md)：曾选 PostgreSQL + Ontop；已由下一票的 Jena 复核结论取代，保留为决策历史。
- [评估 Jena Fuseki/TDB2 作为本体权威库](./issues/33-evaluate-jena-fuseki-as-authoritative-store.md)：TDB2 首选存企业本体、候选及版本，Fuseki 服务读写；首版外部仅业务 API/MCP，后期授权只读 SPARQL，治理与隔离仍由本工程实现。
- [界定 Jena 企业数据集与版本图布局](./issues/34-define-jena-tenant-dataset-and-version-layout.md)：每家公司独立 TDB2 数据集，内部按命名图区分候选、当前与历史版本；跨企业判定由本工程分别读取并按授权返回。
- [界定带范围事实的 RDF 陈述与来源模型](./issues/35-define-rdf-claim-and-provenance-model.md)：带品牌、地域和有效期的事实用可引用的 RDF 陈述表示；同一事实关联多份独立来源，不另写无条件直接三元组。
- [界定 RDF 词汇与 SHACL 校验边界](./issues/36-define-rdf-vocabulary-and-shacl-boundary.md)：五种候选映射到类、属性定义、具体陈述、业务规则和实例；改名沿用 IRI、改义新建；平台基础 SHACL 验结构，企业业务条件仍由已发布规则和 LLM 判定。
- [界定首版基础本体数据服务的范围](./issues/38-define-first-ontology-data-service-scope.md)：第一阶段只建设一甲一乙的本体资料、候选治理、独立版本发布及授权 API/MCP 读取；业务匹配与入围建议在第二阶段，标准文件交换和 SPARQL 留待后期。

## Not yet specified

- 待“行业”被单独定义后，再决定它与采购负责类、品类和企业能力的关系。
- 取得试点资料样本及授权边界后，再细化候选列表和图形化编辑的交互细节。
- 取得试点自然语言样本后，验证从自由表述生成基础业务本体候选的技术路径和质量边界。

## Out of scope

- 本轮不实现代码、部署服务或代替客户验收。
- [RDF/OWL 文件交换契约](./issues/37-define-rdf-owl-exchange-contract.md)留待项目后期；当前优先完成基础本体数据服务，不以文件导入导出作为首版前置条件。
- 不把 LLM 提取结果直接视为已审核本体，也不让未经甲方政策和本次采购授权的推断代替采购审批或正式入围记录。
