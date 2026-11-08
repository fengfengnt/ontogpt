# 买方、供应商 v2 Schema 整合设计

用户要求将 10 份已归档草案整合为买方、供应商各一份 v2，保留 v1，验证后提交并推送 `dev-fengfeng`，暂不部署。用户已明确要求直接实施，无需再次确认设计。

## Approaches

采用按企业在 v1 上累加全部草案的方式，生成两个独立 v2。逐份覆盖同一路径会丢失其他候选；合并买卖方为一个 Schema 会破坏现有企业边界，均不采用。

## 内容与边界

- 买方新增 `quotation_inclusions`、`procurement_unit_price`、`evaluation_committee_size`、`brand_pool_membership`、`volume_discount_tier`、`acceptance_inspection_ratio` 以及关系 `conflicts_with`。
- 供应商新增 `late_payment_penalty_text`、`invited_supplier_names`、`payment_terms_text`。
- 从归档 YAML 原样取得各项定义、描述和类型；不把案例中的人数、金额、比例或品牌设为默认值或业务判定规则。
- 沿用草案的版本方式：`version: v2`，保留基础 Schema 的 `id` 和命名空间，不引入现有术语 URI 迁移。此兼容选择由实施方作出。
- v1 文件、注册项及 10 份原始归档保持不变；新增两个 v2 目录和注册项。Python 使用现有 LinkML 版本确定性生成，不手工修改生成文件。
- 注册只是允许加载；现有启用指针仍须显式切换。本轮不部署、不写运行数据库、不修改草案业务审核状态，也不调用模型或短信。

## 验证与交付

以归档清单核对全部新增项，剔除新增项后应与 v1 结构一致；校验 v1 摘要不变、v2 可加载、生成可重复、旧数据可验证、新字段和关系可保留至候选归一化结果。安装 wheel 后四套模板均应加载成功。

激活测试夹具直接复制真实 v1/v2 和注册表，取消用 v1 伪造 v2 的步骤；保持原来的原子性、企业权限及显式激活断言。通过完整服务测试后独立审阅、提交、推送，并核对远端 SHA。
