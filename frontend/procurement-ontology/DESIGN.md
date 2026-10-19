# 采购知识工作台视觉约定

参考：[Claude 设计分析](https://getdesign.md/claude/design-md)及其 [DESIGN.md](https://github.com/VoltAgent/awesome-design-md/blob/main/design-md/claude/DESIGN.md)。采用暖色纸面、深色正文、克制的陶土色强调和宽松排版；不使用其标志、专有字体或产品名称作为本系统品牌。

## 页面

- 左侧固定导航，右侧为上下文标题和工作区；企业名称只显示本身份绑定的企业。
- 来源、待审与已发布状态使用文字徽标；发布动作有独立确认区。
- 表单使用明确中文标签，表格和证据保留足够阅读宽度。错误在操作区域就近显示，表单内容保留。
- 窄窗口导航换行，属性面板置于图下方；长 ID 和原文可以换行。
- 不使用品牌插画、营销卡片或虚构统计数据。

## 样式边界

`src/styles/tokens.css` 集中定义颜色、字体、间距、圆角和图样式变量。业务组件使用语义变量；Cytoscape 读取同一组变量。背景、正文和按钮文字需保持对比度，不能仅依靠颜色表达状态。焦点可见，表单和按钮可使用键盘操作。

后续改为 [MiniMax 参考](https://getdesign.md/minimax/design-md)等风格时，先更新本文，再修改 tokens 和必要布局，并回归树、画布、来源及问答页。Markdown 不会在运行时自动换肤；MVP 没有主题切换器。
