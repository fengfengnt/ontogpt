# 企业 schema 编写参考

此目录只作参考，不是可启用业务 schema。每家企业、每个二级品类、每个版本都创建独立 YAML 和 LinkML 生成的 Python；即使字段相同也保留自己的文件。

试点完整示例分别位于 `../test_buyer1/computer/v1/`、`../test_supplier1/computer/v1/`。字段说明见 `docs/procurement-ontology/schemas/`。模型只提取业务陈述、适用范围、原文摘录和局部引用；企业身份、正式 ID、来源修订和版本由服务维护。

生成产物和摘要先进入待审版本，经 Git 审阅、测试、部署后，再显式 `activate-schema`。画布不能编辑此处文件，运行服务不生成 Python。
