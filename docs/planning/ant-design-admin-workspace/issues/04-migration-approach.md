# 全量组件迁移的技术路线与验收边界

Type: grilling
Status: open
Blocked by: 01, 02, 03, 05, 06
Map: [OntoGPT Ant Design 管理台与多标签工作台决策地图](../map.md)

## Question

在整个管理台、全部组件迁移的目标下，采用哪条技术路线处理现有业务封装、路由、页内 Tabs、专业控件及页面状态？如何划分实施批次，并用哪些用户可见行为和全量检查证明迁移完成？

以 `frontend/procurement-ontology/` 的实际代码为依据，重新评估 React 工作区状态、Ant Design 控件替换、三级树及 Cytoscape 画布适配。此前针对其他项目的 UI 库和路由判断不能作为本项目的实现基础。

应在真实盘点和前置决策的基础上比较可行方案，由用户选择后写入完整设计；分批实施不能缩减最终交付范围。
