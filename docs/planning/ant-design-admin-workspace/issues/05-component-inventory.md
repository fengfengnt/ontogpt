# 管理台页面与组件迁移清单

Type: task
Status: resolved
Blocked by: none
Map: [OntoGPT Ant Design 管理台与多标签工作台决策地图](../map.md)

## Question

只读盘点管理台路由、共享业务封装、基础控件、表格和表单、专业展示控件与现有测试，明确 Ant Design 的对应能力及没有直接替代项的能力，作为技术路线决策的事实依据。

盘点不安装依赖、不修改产品代码，不根据组件名称相似就认定能力等价。

## Answer

已在用户更正项目后，按 OntoGPT 当前源码完成只读盘点，详细事实及路径见[OntoGPT 当前管理台与迁移影响](../current-state.md)。

- 改造入口为 `frontend/procurement-ontology/`；原 `src/ontogpt/webapp/` 演示独立。
- 管理台使用 React、TypeScript、Vite 和 Cytoscape，没有现成 UI 库、路由库、全局状态库或表单库。
- App 仅保存选中菜单，切换会卸载页面；尚无工作区 tab、关闭确认、全局面包屑或主题切换。
- 手写三级树及本体/关系编辑面板是实际迁移对象；平台和企业菜单按身份隔离。
- 画布有现成布局、版本冲突保留编辑等契约，控件迁移和主题切换不能破坏这些行为。
- 未安装依赖、启动服务或运行测试；以上为源码证据。
