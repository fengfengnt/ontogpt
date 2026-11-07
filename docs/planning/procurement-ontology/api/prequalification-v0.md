# 资格预审判定 API/MCP 最小契约（设计稿）

状态：第二阶段产品接口规格，尚未实现。字段名和操作名用于后续联调，HTTP 路径与具体传输协议尚未冻结。第一阶段只交付[本体数据服务](../phase1-data-service-v0.md)。依据见[资格预审判定 API 决策](../issues/21-define-prequalification-api-contract.md)。

## 边界与调用顺序

外部采购系统保存并确认采购需求、送达乙方、保存乙方响应与正式入围状态。本工程提供企业本体、分类树、知识包、判定政策的已发布版本，以及以下判定能力；内部自动生成待确认本体候选和判定审计。MCP Tools 只调用相同的业务 API，不另写判定逻辑。

1. 采购 Agent 调用[采购草案分析操作](./procurement-draft-v0.md)`analyze_procurement_draft`，用采购员原话、当前草案和企业最新已发布版本取得品类、缺失字段、规则冲突、流程与需重新确认的差异。采购员确认结构化条件快照后，外部系统把该确认快照再次传给同一操作；本工程自动提取新条件候选。外部系统才能按自身流程发布需求。
2. 乙方 Agent 收到外部系统送达的需求后，可调用`evaluate_supplier_admission`进行`SUPPLIER_SELF_CHECK`；甲方 Agent 在本次披露范围内调用同一操作进行`BUYER_ADMISSION`。每次请求只评估**一个乙方**，携带一次采购的全部采购项。一个采购中有多家乙方时，外部系统分别调用。
3. 调用方可用`explain_evaluation`按具体审计引用查询自己有权查看的当时条件、声明、片段、版本和理由。在办判定内部按该事项绑定的已发布快照执行；普通 Agent 的[本体搜索和按 ID 读取](./ontology-read-v0.md)只看最新版，不借审计接口开放任意旧版本体检索。上述操作不发布采购、不邀请乙方、不写正式入围。

## 评估请求

`evaluate_supplier_admission`的最小输入如下。身份和企业权限来自已认证调用上下文，不能仅凭请求体中的企业 ID 授权。外部系统对采购关系、本次披露及自动入围启用提供可核验引用；本工程核验后才读取跨企业资料。

| 字段组 | 必需内容 | 说明 |
| --- | --- | --- |
| 请求与用途 | `request_id`、`purpose`、外部`procurement_id`、`supplier_id`、`evaluated_at`、`stage=PREQUALIFICATION` | `purpose`仅为乙方自检或甲方入围判定；请求标识用于审计和重试 |
| 需求快照 | 采购员原话及版本、已确认结构化快照 ID/版本、确认人/时间引用 | 原话与快照相互矛盾或有遗漏时先返回差异，不作正式判定 |
| 采购项 | 每项 ID、甲方完整三级品类路径与分类树版本、知识包及本体版本、本次数量/预算等取值、条件数组 | 一次请求含全部采购项；每个条件有稳定 ID、原文、`MANDATORY`/`BONUS`、适用阶段、规则引用或`AD_HOC`标记、门槛与评分信息 |
| 采购方式 | `single_supplier_required`；若为否，给出乙方拟响应的采购项 ID | 要求单一乙方时须覆盖全部采购项；否则仅汇总其拟响应项，仍可查看其余项的覆盖情况 |
| 本次自动入围 | 甲方已发布政策版本、本次显式启用及授权引用、入围截止时间、相应品类案例复核启用引用 | 无有效授权也可自检，但不返回“符合自动入围条件” |
| 乙方本次响应 | 逐条件声明或承诺、发言人/服务身份、原话和时间；如已发布能力未覆盖本项，可传本项目临时能力的完整三级路径、各级描述与来源；可选的项目材料文本、来源/版本/有效期/品牌与项目适用范围、披露授权引用 | 声明“有”可单独用于入围判断，不强制上传证明原件；材料原件由外部系统保管；临时路径不是已发布乙方树节点 |

本工程读取被授权的乙方**已发布**本体事实和可供匹配能力，不接受请求体直接伪造本体版本或修改乙方历史事实。乙方为当前项目主动声明且授权披露的临时能力可参与该项目自检和甲方重判，但不进入常规供应商检索。本次乙方声明是独立输入，只作用于本次判定，并生成待确认候选；发布后的可复用范围由乙方管理员确认，规则见[乙方本体结构](../ontology/supplier-model-v0.md)。

临时能力作为`supplier.temporary_capabilities[]`传入，至少包含`project_id`、`declaration_ref`、三级路径每级的名称和描述、原话来源、声明身份/时间及披露授权引用。若引用的是已发布但未打开检索标记的能力，还要带已发布能力引用；若路径含新节点，须标明其为临时节点而非伪造已发布节点 ID。路径或描述不足以判断等价时仍返回`UNCERTAIN`，不因乙方声称可供应就跳过品类初筛。

## 判定顺序与结果

1. **验证需求**：程序检查身份权限、必填字段、数据类型、规则引用、版本与权重合计；LLM 对照原话与已确认快照，判断业务含义、条件适用性及甲方已发布硬约束是否冲突。本次人工输入可覆盖知识包默认建议，不能覆盖甲方硬约束。原话与快照不一致、触犯硬约束，或 LLM 无法确定是否冲突时，返回`demand_validation=NOT_READY`，列出差异、冲突或待澄清问题，`overall_result=null`；采购员补充并重新确认快照后重试。企业硬约束按其本体规则所声明的范围生效，即使知识包漏写引用。
2. **品类初筛**：仅在甲方发布需求或对该需求明确重判时，比较甲乙方完整三级路径及说明。常规供应商检索只使用已发布且标为可匹配的乙方能力；针对当前项目的乙方声明可带临时完整路径参与该项目评估，结果标明`TEMPORARY_DECLARATION`，不伪称已发布能力。固定版本相似度达到高阈值且 LLM 判断`EQUIVALENT`才为`MATCH`；低于低阈值为`NO_MATCH`；中间、包含关系、缺描述或模型失败为`UNCERTAIN`。品类匹配不代替条件判定。
3. **逐条件判断**：已发布条件的原文和判定说明、本次参数以及新`AD_HOC`条件均交给 LLM 作业务判断，包括数值比较。LLM 可关联已发布乙方本体、本次材料和逐条件声明。逐条件正面诚信声明即使没有附件也可作为“满足”的依据。若声明与乙方已发布事实相反，仍以本次声明作本次入围判断，同时返回`published_fact_conflict`，并把声明送入乙方待确认候选；既不改写旧事实，也不静默抹去冲突。完全没有与条件相关的已发布内容、本次材料或**逐条件声明**时返回`MISSING`；无法判断返回`UNCERTAIN`，明确反向声明或条件判断失败返回`UNSATISFIED`。相关文本的高相似度只是找线索，不能单独代表“满足”。
4. **汇总**：必须项门槛须逐项通过，0 分的计分必须项不通过；加分项不阻断准入。单供应商采购须全部采购项覆盖并通过，多供应商采购按乙方拟响应项汇总。优先级为明确失败`不满足`，其次必要资料/声明缺失`待乙方补资料`，再其次语义或判断不确定、自动授权缺失`待甲方核验`，最后在政策与本次授权均有效时返回`符合自动入围条件`。入围截止后仍缺的必须项按`不满足`处理。冲突标记本身不推翻采购员已接受的乙方本次声明。

逐采购项返回品类三态、相似度、LLM关系及版本；逐条件返回`SATISFIED`、`UNSATISFIED`、`MISSING`或`UNCERTAIN`、适用规则、分数/门槛、判定方式、可见依据及理由。声明依据须标记`SUPPLIER_DECLARATION`，与`PUBLISHED_ONTOLOGY`及`PROJECT_MATERIAL`区分；不把“乙方自述”写成“已核验证明”。总响应携带四态汇总、用途、两侧本体/分类版本、知识包/政策/模型/阈值版本、候选引用和审计引用。乙方自检结果只向乙方说明建议，不向外部系统声称已正式入围。

## 自动生成待确认本体候选

采购员**确认本次条件快照后**，`analyze_procurement_draft`或首次`evaluate_supplier_admission`发现知识包未定义的新条件，便自动为甲方创建待确认候选；乙方本次逐条件声明提出其已发布本体没有的能力或事实时，评估操作自动为乙方创建待确认候选。乙方临时路径中缺失的树节点也入分类树待确认队列。外部 Agent 无须调用“提交候选”接口。候选保留原话、说话人/调用身份、时间、采购项/项目来源、原文明确的品牌/地域/品类/项目限制、来源快照或响应引用。首版先按“企业 + 来源快照/响应 ID + 条件 ID”保证重试不重复，再按“企业 + 候选类型 + 二级品类 + 适用范围 + 规范化原文”合并完全相同的候选并追加来源；只在措辞上相似的候选仍分开供管理员判断等价。若新声明与已发布乙方事实冲突，候选明确标记冲突供管理员处理；本次声明仍可用于本次入围判断。

候选不自动成为已发布本体事实。候选进入本企业未分批待审队列，可并入当前唯一待发布批次；只有本企业有确认权限的人采纳、企业管理员发布新本体版本后，才供后续新事项作为已发布内容读取。乙方管理员发布可复用能力或服务承诺后，默认供未来适用采购读取；原文或材料明确的项目限制仍保留。新能力进入常规检索，还须管理员在发布时明确确认`可供采购匹配`标记。内部候选写入不等于本工程接管采购需求或入围台账。

## 权限与审计

- `BUYER_ADMISSION`的常规查找只能读取乙方标记可供匹配的已发布能力；针对当前采购，亦可读取乙方主动声明并授权披露的临时能力及本次声明和材料。`SUPPLIER_SELF_CHECK`只读取该乙方自身及获授权的甲方需求。返回的片段也按相同范围裁剪。
- 判定审计记录外部采购与快照引用、实际调用身份、判定时间、甲乙双方版本、规则/模型/阈值、条件输入、逐项理由、声明的可信来源类型、冲突和候选引用。外部系统仍负责事后发现错误的业务处置。
- 权限失败、无效版本或无法核验授权属于接口错误或`待甲方核验`，不得伪装为`符合自动入围条件`。本工程返回“符合条件”也不代表外部系统已经邀请乙方。

## 联调示例（虚构数据）

采购员确认“采购 100 台笔记本；乙方须提供五年维保”。乙方已发布本体写有“三年维保”，但本次逐条件声明“这个项目可提供五年维保”，无附件。若品类高阈值等价，甲方规则允许以本次诚信声明判断，甲方政策及本次授权有效，且其他必须项通过，则本工程可返回该维保条件`SATISFIED`、依据类型`SUPPLIER_DECLARATION`、冲突`published_fact_conflict`及整体`符合自动入围条件`。乙方该项目五年维保声明自动成为待确认候选；外部系统决定是否正式邀请。这里没有假定任何模拟案例中的供应商已经具备这些事实。

第二种情况：采购员原话“餐标 250 元/人”，而企业已发布硬约束为不超过 200 元/人。无论乙方怎样声明，本工程返回`NOT_READY`和硬约束冲突，不进行正式入围判断；本次确认值不能修改企业硬约束。

以下 JSON 仅演示一个采购项、一个乙方和一个本次新增必须项的**字段形状与语义**；所有 ID、版本、分数及事实均为虚构。示例的单项满分为 100，实际项目可有多项条件，但同一采购项的可计分满分仍须合计 100。

```json
{
  "request_id": "eval-demo-1",
  "purpose": "BUYER_ADMISSION",
  "procurement": {
    "id": "purchase-demo-1",
    "stage": "PREQUALIFICATION",
    "evaluated_at": "2026-10-16T12:00:00+08:00",
    "deadline": "2026-10-20T18:00:00+08:00",
    "single_supplier_required": true,
    "original_text": "采购100台笔记本，乙方需承诺五年维保",
    "original_text_version": "text-1",
    "confirmed_snapshot_ref": "snapshot-1",
    "confirmed_by_ref": "buyer-user-1",
    "confirmed_at": "2026-10-16T10:00:00+08:00"
  },
  "items": [
    {
      "id": "item-1",
      "buyer_category_path": ["IT与通讯", "办公设备", "电脑(台式机/笔记本)"],
      "buyer_tree_version": "buyer-tree-v1",
      "knowledge_pack_ref": "laptop-pack-v1",
      "values": {"quantity": 100, "unit": "台"},
      "conditions": [
        {
          "id": "condition-1",
          "kind": "AD_HOC",
          "text": "乙方需承诺五年维保",
          "role": "MANDATORY",
          "max_score": 100,
          "min_pass_score": 1
        }
      ]
    }
  ],
  "supplier": {
    "id": "supplier-demo-1",
    "declarations": [
      {
        "condition_id": "condition-1",
        "text": "本项目可提供五年维保",
        "actor_ref": "supplier-user-1",
        "stated_at": "2026-10-16T11:30:00+08:00",
        "project_id": "purchase-demo-1",
        "disclosure_ref": "disclosure-1"
      }
    ],
    "materials": []
  },
  "auto_admission": {
    "enabled": true,
    "policy_ref": "buyer-policy-v1",
    "authorization_ref": "purchase-auth-1",
    "category_review_ref": "laptop-review-1"
  }
}
```

假设乙方已发布本体有可匹配的电脑供应能力，但旧维保事实仅为三年；品类高阈值等价、LLM 对该声明判满足、上述授权全部有效且其余校验通过时，响应的关键部分为：

```json
{
  "request_id": "eval-demo-1",
  "demand_validation": {"status": "READY", "differences": [], "hard_rule_conflicts": []},
  "items": [
    {
      "id": "item-1",
      "category_match": {"status": "MATCH", "relation": "EQUIVALENT", "basis_ref": "match-audit-1"},
      "conditions": [
        {
          "id": "condition-1",
          "status": "SATISFIED",
          "score": 100,
          "method": "LLM_AD_HOC",
          "basis": {"type": "SUPPLIER_DECLARATION", "text": "本项目可提供五年维保", "actor_ref": "supplier-user-1", "stated_at": "2026-10-16T11:30:00+08:00"},
          "published_fact_conflict": {"fact_ref": "supplier-warranty-v1", "description": "旧本体记载三年维保"},
          "reason": "本次逐条件声明承诺五年维保；按诚信申报用于资格预审"
        }
      ],
      "result": "符合自动入围条件"
    }
  ],
  "overall_result": "符合自动入围条件",
  "candidate_refs": ["buyer-candidate-1", "supplier-candidate-1"],
  "versions": {"buyer_ontology": "buyer-v1", "buyer_tree": "buyer-tree-v1", "supplier_ontology": "supplier-v1", "supplier_tree": "supplier-tree-v1", "knowledge_pack": "laptop-pack-v1", "policy": "buyer-policy-v1", "matcher": "matcher-v1", "llm": "llm-config-v1"},
  "audit_ref": "evaluation-audit-1"
}
```

响应中没有“已正式入围”字段；本工程不掌握该业务状态。外部系统不应把乙方自检结果当作邀请记录。实际响应须对有权调用者返回完整逐项判定依据，并按访问权限裁剪乙方内容。
