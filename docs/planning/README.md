# 设计资料与历史快照

本目录收录此前仅存于本地临时目录的项目设计资料和独立原型源码，供追溯需求及继续评审。纳入版本管理不表示批准新功能、完成实现或部署；原临时文件保持不变。

| 资料 | 定位与边界 |
| --- | --- |
| [采购本体产品决策地图](procurement-ontology/map.md) | 早期完整产品讨论、问题票据、候选接口与研究资料；部分设想超出已经实现的 MVP，当前契约与验收以[采购本体文档](../procurement-ontology/README.md)及实际源码为准。 |
| [Ant Design 管理台设计地图](ant-design-admin-workspace/map.md) | 多标签工作区、三主题及管理台迁移的需求和待评审设计，尚未实现为正式管理台。 |
| [管理台独立原型](ant-design-admin-workspace/prototype/README.md) | 仅使用本地模拟数据，保留可编辑源码和锁文件；HTML 编译产物、依赖目录及预览截图不入库。原文“已执行的检查”属于制作当时的历史记录。 |
| [OntoGPT 架构数据](../../ontogpt.architecture.json) / [可分享 HTML](../../ontogpt.architecture.html) | 既有静态架构交付快照，元数据固定来源提交 `9224d33f84cce7097c3519e1d9f0e2be46cec056`；不代表后续采购本体、SSO 或当前部署的完整架构。视觉检查截图和本地检查报告不入库。 |

OpenSpec 项目入口为根目录 `openspec/config.yaml`，配套项目技能保存在 `.agents/skills/`。本次仅保存既有配置和生成的技能内容，不创建新 OpenSpec 变更或扩展实现范围。
