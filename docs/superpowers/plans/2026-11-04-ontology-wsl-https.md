# Ontology WSL HTTPS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 将采购本体服务以镜像接入 `https://ontology.lvh.me`，保留现有数据与 Git 草案。

**Architecture:** `yunhezhiyuan` 项目新增 `ontology-app`、`ontology-fuseki`；共用 Nginx 继续代理宿主 8002。应用代码和 schema Git 工作树按发布版本持久化，SQLite 与 Fuseki 独立持久化。

**Tech Stack:** Python、FastAPI/Uvicorn、React/Vite、Docker Compose、既有 Nginx、Fuseki/TDB2、SQLite、Git。

**Spec:** `docs/superpowers/specs/2026-11-04-ontology-wsl-https-design.md`，用户已批准实施。

## Global Constraints

- Compose 项目 `yunhezhiyuan`；本项目容器和一次性容器均以 `ontology-` 开头。
- 复用共用证书和 Nginx，保留其他应用配置、数据、issuer。
- 仅一个应用 worker；沿用现有 Fuseki 卷，不允许两个 TDB2 写入者。
- 密钥只在私有运行文件加载，不提交 Git、不进入镜像。

## Review Focus

- HTTPS 同源写与 MCP Host/Origin：任务 1 测试精确允许与拒绝，旧 HTTP 测试保留。
- 非可信代理伪造 scheme：任务 1 测试 proxy peer，不使用全网段信任。
- 重建/升级被旧代码卷遮蔽：任务 2 测试发布标识和初始化失败关闭。
- Windows 草案与 SQLite 数据损失：任务 3 迁移前逐工作树归档、双库备份和摘要核验。
- 共用 Compose/入口误操作：任务 3 只创建 ontology 服务，核对其他容器基线与 SSO issuer。

### Task 1：代理与 HTTPS 适配

**Files:** 修改 `procurement_ontology/api.py`、`runtime.py`（均相对 services/procurement_ontology）；新增 `tests/unit/test_https_deployment.py`。

**Interfaces:** `create_app(..., public_origin=None)`；环境 `PROCUREMENT_PUBLIC_ORIGIN`、`PROCUREMENT_BIND_HOST`、`PROCUREMENT_TRUSTED_PROXIES`。

- [x] 新增 HTTPS 登录 Secure Cookie、退出、错误 Origin/Host、MCP HTTPS、非可信 proxy peer 测试，运行并观察失败。
- [x] 实现最小显式部署配置；保留原 HTTP 默认；仅允许精确公开 Origin 与代理地址。
- [x] 用现有 Python 运行环境运行相关及服务测试，通过后提交。

### Task 2：可追溯镜像和持久化工作树

**Files:** 新增 `deploy/ontology/Dockerfile`、`compose.yaml`、`entrypoint.py`、`prepare-build.py`、`deployment.env.example`、`README.md`；新增入口初始化单测。

**Interfaces:** 镜像种子 `/opt/ontology-seed`；发布目录 `/workspace/releases/<release-id>`，新草案 `/workspace/drafts`；私有运行目录 `/runtime`。

- [x] 先测相同版本复用、版本隔离、种子校验失败关闭以及未审核文件不进入构建上下文。
- [x] 用 Git archive/显式复制创建无秘密构建上下文；Node 构建前端、uv locked 安装 Python 依赖，镜像内初始化无远端凭据 Git 基线。
- [x] 入口按版本初始化工作树，设置实际运行代码导入路径，校验种子摘要；Compose 使用 external Fuseki 卷和单独 bridge 网络。
- [x] 构建镜像、测试入口，提交文件；记录实际镜像摘要。

### Task 3：备份、迁移与部署

**Files:** 私有 WSL `/home/fengfeng/yunhezhiyuan/ontology/`，必要时仅修改共用 Nginx 的 ontology 站点；记录操作证据到运行目录。

- [x] 保存原容器/挂载/业务版本基线；确认旧应用未写入，运行现有双库备份；逐 Windows Git 草案保存分支及未提交内容。
- [x] 将 SQLite 和凭据安全复制到 WSL，改为容器内路径并保留数据集前缀；记录唯一活动目录。
- [x] 停止旧 Fuseki，组合现有 Compose 与 ontology 片段，只启动 ontology 两个服务并复用旧卷；旧容器保留停止以供回退。
- [x] 实测代理 peer 后限定可信地址；按需仅给 ontology 站点增加 Docker 网关 HTTPS 接入，校验并生效。
- [x] 严格 CA 验证 Windows、WSL、Docker 网络客户端；验证无错误登录/跨域放行，并核对其他容器、SSO issuer 保留。

### Task 4：验收、复核与交付

**Files:** `docs/procurement-ontology/deployment-2026-11-04.md`，本计划状态。

- [x] 运行服务测试、前端构建与部署实际请求；验证应用重建后的数据和 Git worktree 保留。
- [x] fresh-context 审阅整个实现，修复重要问题并运行覆盖测试；记录未执行的真实模型和 UAT 测试。
- [x] 提交实现与中文运维说明，交付 HTTPS 地址、容器/数据位置、启动/停止/备份命令和实际验证边界。

## 执行记录

用户“实施”授权直接完成全部任务；采用当前任务内执行与最终独立审阅。既有主工作区旧 Web 演示修改保留在原处。


Task 1: 65a5de49，HTTPS 测试 RED→GREEN，相关17项通过，最终服务套件124 passed/1 skipped。
Task 2: 1af06992，发布工作树3项通过，镜像及前端构建完成，镜像内schema摘要通过。
Task 3: 双库备份、4账号迁移、10草案归档、同卷迁组、HTTPS与Docker入口完成；旧容器改名ontology-fuseki-before-migration并保持停止。
Task 4: Windows严格CA的34项HTTP/API检查通过，Docker边界5项通过，真实重建和新部署CLI备份通过；共用40容器保留及issuer8443不变。
Final review: 独立审阅未发现Critical/Important。
Final: minor (deferred): public_origin非法端口/显式默认端口的提前规范化校验；当前精确Origin正常。
Ruling: Windows→WSL SQLite迁移改用已完成离线备份文件复制及WSL原生完整性检查——跨系统路径SQLite锁停滞，原库未受影响。
Ruling: Git实现分支保留供审阅，不自动合并main或推送；实际镜像部署已完成，代价是源分支整合仍需用户决定。
