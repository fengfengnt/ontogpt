# OntoGPT 当前管理台与迁移影响

本轮需求已从误选项目迁移到 `D:\Code\ontogpt`，已确认的用户交互决定继续有效。本文仅记录当前源码事实和设计影响，未实施产品代码，也未执行浏览器、模型或服务验证。

## 范围

- 管理台：`frontend/procurement-ontology/`，服务于平台管理、企业管理和企业只读用户。
- 后端：`services/procurement_ontology/`，已有企业隔离、候选审核、版本发布、schema 激活及 API/MCP 边界；本次界面需求不授权变更这些业务规则。
- 旧演示：`src/ontogpt/webapp/` 使用 FastAPI/Jinja2，保持独立；既有本地修改保留。
- 既有产品边界继续参考 `docs/planning/procurement-ontology/map.md`、`docs/procurement-ontology/` 和服务 README，本轮不改写原产品决策地图。

## 当前事实

| 领域 | 当前实现及证据 | 对本轮设计的影响 |
| --- | --- | --- |
| 前端依赖 | `frontend/procurement-ontology/package.json:11` 仅有 Cytoscape、React、React DOM；构建脚本为 `tsc --noEmit && vite build` | 不能套用其他项目的 Base UI/shadcn、TanStack Router、Zustand 或表单库结论；Ant Design 与工作区机制需要重新设计 |
| 菜单与身份 | `src/App.tsx:16` 使用本地 `tab` 状态；`:33` 按角色生成菜单；`:36` 选择首菜单 | 菜单 tab 的标识及默认入口必须结合平台/企业/只读身份，不得暴露未授权菜单 |
| 页面生命周期 | `src/App.tsx:48` 使用 `selected + refresh` 作为页面 key，随后条件渲染单一页面 | 切换会卸载本地表单；不能只增加 Tabs 外观。来源 tab 数据刷新须与其他 tab 的编辑状态保留一起设计 |
| 默认菜单 | 当前首菜单分别为平台“通用本体”、企业管理员“资料与提取”、只读用户“本体画布” | 原“概览”示例在本项目没有现成对应页，须确认默认回落规则 |
| 三级树 | `src/TreeEditor.tsx:31` 递归手写 `ul/li/button`；`:20`、`:55` 限制第四层，`:27` 第三级需 `category_key`，`:28` 提交 `observed_version` | 适合用 Ant Design Tree 重做交互；保留层级、品类键和版本校验契约 |
| 功能表单 | `src/OntologyCanvas.tsx:112`、`:113` 新增条目/关系，`:127`—`:134` 右侧表单；`src/PlatformEditor.tsx:51`—`:53` 通用本体编辑；`src/ManagementPages.tsx:112` 候选修订 | 将实际业务编辑功能映射到独立功能 tab，并记录发起操作的来源 tab；“新增用户”只作为通用交互示例 |
| 本体画布 | `src/OntologyCanvas.tsx:71` 创建 Cytoscape，`:76` 使用 breadthfirst 布局，`:78`—`:85` 读取颜色 tokens，`:92` 卸载时销毁 | 技术方案须说明专业画布与 Ant Design 的边界；隐藏/显示时的尺寸、视口和主题更新需要验证 |
| 主题 | `src/main.tsx:3` 导入 `styles/tokens.css`；tokens 文件只有单套浅暖色 `:root`，没有 ThemeProvider 或偏好保存 | 三种主题是新增能力；除普通控件外还需让已创建的画布更新颜色，不能通过整体重建丢掉编辑状态 |
| 现有回归 | `src/App.test.tsx` 覆盖菜单隔离和三级树；`src/OntologyCanvas.test.tsx` 覆盖版本冲突保留编辑；`src/ManagementPages.test.tsx` 覆盖过期候选重审；`src/CanvasLayout.test.tsx` 覆盖节点不重叠 | 迁移时保留这些契约，并补充多 tab 保留、复用、关闭确认、来源页返回刷新、菜单/面包屑联动及三主题回归 |

表中的 `src/` 相对路径均以 `frontend/procurement-ontology/` 为根。上述测试仅核对了源码及其覆盖意图，本轮没有重新执行。

## 后续方案讨论的依据

- 用户需求和已确认交互规则保持不变，重新评估的是它们在 OntoGPT 中的实现方式。
- 当前代码没有现成路由或状态管理约束；是否增加路由库、如何保存存活页面、如何刷新来源页，应比较实际可行方案后确定，不能照搬原项目。
- Ant Design 覆盖有对应能力的界面控件；专业本体画布、业务编辑语义与权限边界的适配需要在完整设计中写清，尚未批准替换或删除这些能力。
- 浅色、暗黑、绿色护眼三种主题已确定；默认主题、具体外观、切换入口和偏好保存策略仍待讨论。
