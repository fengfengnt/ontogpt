# Ontology SSO 0.1.1 本地 WSL HTTPS 发布记录

日期：2026-11-04。状态：**已发布、健康及数据保留核验通过；真实 SSO 登录待 client 凭据**。

## 访问地址

| 用途 | 实际 HTTPS 地址 |
| --- | --- |
| 前端工作台 | https://ontology.lvh.me/ |
| 用户名密码登录 | https://ontology.lvh.me/login/password |
| 后端接口文档 | https://ontology.lvh.me/docs |
| 后端 API 前缀 | https://ontology.lvh.me/v1/ |
| 健康检查 | https://ontology.lvh.me/health |
| MCP | https://ontology.lvh.me/mcp/ |

前后端由同一镜像提供，通过共用 Nginx 的 HTTPS 域名访问；8002 上游只绑定本机 loopback，不作为对外交付地址。

## 版本、镜像与归档

- 用户选定发布版本 **0.1.1**，项目根目录新增 `VERSION`，WSL 同步到 `/home/fengfeng/yunhezhiyuan/ontology/VERSION`。
- Compose 分组：`yunhezhiyuan`；应用服务键保留 `ontology-app`。
- 应用镜像：`yunhezhiyuan-ontology-0.1.1:local`。
- 应用容器：`yunhezhiyuan-ontology-0.1.1`，状态 healthy。
- 镜像 ID：`sha256:8e0f6c7c194bcee4e6762f1a891dd0ff97707a78ae6aa878f442cf2153927135`。
- 来源 HEAD：`ee4617a2e0fb8544aec28fe5d9c58b8b139a5843`，包含未提交的 HTTPS 部署整合；实际输入以内容指纹 `1351778e2ff06fb73cd9459f1e581403d457b1f9` 和归档 `source-inputs.json` 为准。没有创建 Git 提交或推送。
- 统一归档：`D:/Code/deploy/local-deploy/releases/yunhezhiyuan-ontology/local/0.1.1/`，包含可 docker load 的镜像包、构建上下文、实际 Dockerfile、公开配置、SHA256SUMS 与发布记录；不含运行秘密或数据库备份。
- 应用镜像发布版本取自 VERSION；Python/npm 分发包版本属于依赖元数据，仍保留原值，不作为发布版本。

## 构建与源文件边界

复用既有 HTTPS 代理信任、独立发布 Git 工作区和数据挂载流程，与已经实现的 SSO 合并。构建在隔离工作区完成，本次源码和 VERSION 已同步回 `D:/Code/ontogpt`，原 Web 演示的无关本地修改保留。构建器允许本次未提交代码，但只导出已跟踪应用路径及显式 VERSION/Dockerfile/entrypoint 白名单；运行目录、凭据、宿主 Git 历史不进入上下文。

常规构建中依赖下载停滞，确认 Docker 阶段未继承 WSL 代理；传入代理后的单次重试出现 TLS 握手失败，停止重复联网下载。最终以原已验证镜像的固定摘要为依赖基础，核对 234 个已安装分发包均属于 uv.lock，并在 `--network none` 下执行 `uv sync --locked --offline` 成功，只重建两个本地源码包。前端使用已测试构建，实际离线构建配方已进入归档，不降低锁定依赖或 TLS 要求。

## 数据、配置与回退

- 原运行目录 `/home/fengfeng/yunhezhiyuan/ontology/runtime`、工作区 `/home/fengfeng/yunhezhiyuan/ontology/workspace`、Fuseki 身份文件和外部数据卷保留。
- 只停止/替换应用；Fuseki 容器、镜像、卷及其余 27 个容器 ID 保持。共享后端 VERSION 仍为 0.1.0，没有改共享 Nginx 或认证中心。
- 切换前双库备份：`/home/fengfeng/yunhezhiyuan/ontology/runtime/backups/pre-sso-0.1.1/manifest.json`；受限配置备份：`/home/fengfeng/yunhezhiyuan/ontology/backups/pre-sso-0.1.1-config/`，均留在目标 WSL，不进入发布归档。
- 备份 SQLite 完整性、外键和所有文件 SHA256 校验通过。切换后 accounts 4、companies 3、sessions 29、service_tokens 10、active_schemas 2、schema_activation_audit 2，全部旧表逐行与备份相同；新增 SSO 表为空，没有重建账号或分配企业。
- 4 个 RDF 域分别为 platform 127、test_buyer1 418、test_buyer2 32、test_supplier1 228 四元组；逐图与备份同构，树/本体发布版本保持。
- 原工作区 897 个文件摘要保持，新版本只增加独立内容指纹发布目录，不覆盖旧发布或草案。
- 原模型配置和身份凭据保留，仅准备正确本地 SSO issuer 与 callback；没有生成或复用 client 凭据。

旧镜像 `ontology-app:local-20261104-1af0699` 保留。回退需先停止新应用，再恢复受限配置备份中的原 Compose/deployment.env，使用同一最新 runtime、workspace 和 Fuseki 数据启动旧应用；不能清卷或用旧 SQLite 覆盖新业务写入。

## 网络、CA 与验证

- `sso.lvh.me:host-gateway` 解析到现有可信入口 172.17.0.1；现行 issuer 为 `https://sso.lvh.me`，不使用已关闭的 8443。
- CA bundle 将原标准公共根证书和现有公开 local-ca.pem 合并，只读挂载 `/secrets/ca-bundle.pem`；SSL_CERT_FILE/REQUESTS_CA_BUNDLE 使用该 bundle，保留 121 个受信 CA，不挂载私钥、不关闭校验。
- 运行容器内严格 TLS 的新 Discovery/JWKS 均通过；公钥摘要与中心保持 `95e08466aa1697674540419be3d535fc92a33b004d839576b849f3120a3b2b6a`。
- 本轮服务完整测试 **114 passed、47 skipped**；跳过项依赖外部 Fuseki 测试环境，不计为通过。前端 **18 passed**，TypeScript/Vite 构建通过。HTTPS/容器包装脚本新检查先失败再通过，独立代码审查未发现发布阻断问题。
- 实际 HTTPS 检查 16 项通过：前端、密码路径、引用资源、健康、接口文档、匿名身份/平台/MCP拒绝、错误 Origin/CSRF拒绝、代理覆盖外来 scheme、SSO 配置及路由已部署。
- 独立 Docker 客户端的假 HTTPS 代理头被拒绝，错误 Host 被拒绝；Compose 包装脚本验证应用/共享后端分别读取各自 VERSION，支持 CRLF。

## 启停与后续 SSO 配置

```bash
bash /home/fengfeng/yunhezhiyuan/ontology/compose.sh config --quiet
bash /home/fengfeng/yunhezhiyuan/ontology/compose.sh up -d --no-build --no-deps ontology-app
```

`compose.sh` 从本体自己的 VERSION 读取应用版本，再调用共用包装脚本独立读取共享后端版本。不要执行 down -v、remove-orphans 或重建其他服务。

用户后续将 client ID 和 secret 写入 WSL 私有 `ontology/runtime/.env` 的 `PROCUREMENT_SSO_CLIENT_ID`、`PROCUREMENT_SSO_CLIENT_SECRET`；认证中心精确登记 callback `https://ontology.lvh.me/v1/auth/sso/callback`。仅配置变更时沿用同一镜像并 recreate 本应用，使 env_file 生效；不要只改 Windows 回退配置或把秘密发到聊天/写入归档。

当前 `/v1/auth/sso/config` 实际返回 enabled=false，发起 SSO 返回 503 安全拒绝，前端提供密码入口。未执行真实 SSO 登录、浏览器人工登录、短信、付费模型调用或 UAT/生产发布。
