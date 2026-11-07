# 工作树合并与清理记录

日期：2026-11-07。最终开发主线：`dev-fengfeng`，主目录 `D:/Code/ontogpt`。本次不部署、不重建容器、不修改运行数据库或私有 SSO 配置。

## 合并范围

- `codex/ontology-sso` 和 `codex/procurement-knowledge-service` 的提交已包含在主线。
- 合并 `codex/ontology-wsl-https` 的三个独有提交。冲突保留主线较新的 SSO、VERSION、CA 信任、镜像命名和测试实现，补入初次 HTTPS 部署的历史记录与计划；没有回退到旧镜像配置。
- 主目录原有的 Web 演示改动一并提交：DeepSeek 模型选项、当前模板响应接口兼容、Schema 选项显示与表单宽度，以及既有回归测试和配置说明。
- 原有 OpenSpec、本地工具配置、架构导出和原型草稿保留在主目录，没有将本地索引、运行秘密、依赖缓存或构建上下文加入 Git。

## 工作树与资料保留

用户明确选择保留业务草案独立，仅合并开发工作树并清理旧树。

- 已移除 `ontology-sso`、`ontology-wsl-https`、`procurement-knowledge-service` 三个已合并开发工作树的 Git 注册及对应本地开发分支；不删除 `main` 或远端分支。`ontology-wsl-https` 和 `procurement-knowledge-service` 旧目录已完全移除；`ontology-sso/ontogpt` 仅剩被当前会话占用的空目录（零文件），未强行结束当前应用来删除它。
- 清理前确认开发工作树没有正在运行的应用进程引用。临时资料、旧运行数据、旧凭据目录和评审记录移入本地私有归档 `D:/Code/ontogpt-worktree-archives/20261107/`，1,222 个文件逐一校验 SHA-256；另保留并验证完整 Git bundle。
- 保留全部 10 个 `D:/Code/procurement-schema-drafts/gap-*` 工作树。它们仍由当前 RDF 数据库的 `DRAFT` 记录引用，20 个 YAML/Python 文件摘要均与业务记录一致；未修改草案、合并候选版本、注册或启用 v2 Schema。
- 运行服务使用 WSL 中的独立发布目录，本次源码工作树整理不切换运行版本。

## 验证

- 后端完整测试：114 passed、47 skipped；跳过项依赖外部集成测试环境，不计作通过。另有两项原有依赖弃用警告。
- 前端完整测试：18 passed，TypeScript/Vite 构建通过。
- Web 演示回归测试：1 passed；仅检查页面，不执行真实模型调用。
- 合并冲突和差异检查通过。主目录原有文件、业务草案及受限归档另做保留核验。

未执行真实 SSO 用户登录、短信、付费模型、UAT 或生产部署。本地文件归档不进入远端 Git。
