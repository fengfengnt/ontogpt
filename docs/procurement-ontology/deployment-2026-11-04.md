# 2026-11-04 WSL Docker 与共用 HTTPS 部署记录

## 当前入口与运行对象

访问 `https://ontology.lvh.me/`。网页、`/v1/` API、`/mcp/` 经既有 `yunhezhiyuan-nginx` 转发至本机 8002；使用原有本地 CA 和通配证书。采购服务继续使用自己的身份、会话和企业服务令牌，本次未接入统一 SSO。

| 对象 | 实际值 |
| --- | --- |
| Compose 项目 | `yunhezhiyuan` |
| 应用容器 | `ontology-app`，单 worker，宿主仅 `127.0.0.1:8002` |
| 应用镜像 | `ontology-app:local-20261104-1af0699` |
| 实际应用镜像 ID | `sha256:6d476c58c17689941657dac32dadfcb7bcbb9226c55744dfd3b0da0b1a98fbd6` |
| 镜像源码提交 | `1af06992d659f0dd8e5d5f1ab437884b8a7a8131`；之后的文档提交不代表另一次镜像构建 |
| Fuseki 容器 | `ontology-fuseki`，沿用 `procurement-fuseki:6.2.0`，宿主仅 `127.0.0.1:3032` |
| 原 Fuseki 数据卷 | `procurement-ontology_fuseki_data`，以 external volume 原位复用 |
| 已停止的原 Fuseki | 改名 `ontology-fuseki-before-migration`，保留原容器 ID、镜像与卷供回退；不得与新 Fuseki 同时启动 |
| 本项目部署目录 | `/home/fengfeng/yunhezhiyuan/ontology` |
| Docker bridge | `yunhezhiyuan_ontology` |
| 实测代理 peer | `172.27.0.1`，只信任此单个地址 |
| 容器内 Fuseki URL | `http://ontology-fuseki:3030` |

共享入口及全站域名记录的权威文件仍为 SSO 工程 `docs/deployment/local-wsl-yunhezhiyuan.md`；本记录不维护其他应用的部署清单。

## 数据与凭据保留

- 迁移前已通过现有 CLI 完成双库备份。备份位于原 Windows 运行目录 `backups/wsl-https-20261104/`，WSL 副本为 `ontology/backups/pre-migration/`。
- 复制已完成的离线 SQLite 备份，并在 WSL 原生 SQLite 执行完整性校验；没有通过跨系统共享路径直接打开目标库进行迁移写入。4 个原账号、schema 启用状态与所有发布版本均保留。
- 唯一活动 SQLite 为 `ontology/runtime/control.sqlite3`。原 Windows `services/procurement_ontology/runtime/` 为回退副本，不能再作为同一数据集前缀的写入服务启动。
- 模型设置与既有凭据转入 `ontology/runtime/.env`，权限 600；Fuseki 身份文件在 `ontology/secrets/` 只读挂载。未生成替代密码或轮换口令，凭据未进入 Git、构建上下文和镜像。
- 10 个旧 Windows schema 草案均保留原工作树，并另存 Git bundle、逐工作树差异、未跟踪文件和原路径。归档位于 `ontology/backups/windows-drafts/`；未自动重新生成或激活。
- 新代码及 Git 元数据在 `ontology/workspace/releases/<镜像源码提交>/`，新草案位于 `ontology/workspace/drafts/`。每次发布从镜像种子初始化独立仓库，不挂载宿主完整 Git 历史；重建时校验文件摘要。
- 迁移后还实际运行过新部署的备份命令，清单位于 `ontology/runtime/backups/post-migration-20261104/manifest.json`。

## 启停与备份

从 WSL 执行，命令只操作本项目服务：

```bash
cd /home/fengfeng/yunhezhiyuan
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml ps ontology-app ontology-fuseki
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml up -d --no-build --no-deps ontology-fuseki ontology-app
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml stop ontology-app ontology-fuseki
```

备份时只停止应用，保留 Fuseki 运行，具体命令见 [部署说明](../../deploy/ontology/README.md)。不要对共享项目执行 `down`、`--remove-orphans` 或删除数据卷。

## WSL 系统和 Docker 客户端调用

原生 WSL 使用既有公开 CA 文件 `/home/fengfeng/yunhezhiyuan/certs/local-ca.pem` 校验 HTTPS。Docker 调用方将 `ontology.lvh.me` 解析到宿主网关，例如 `extra_hosts: ["ontology.lvh.me:host-gateway"]`，并只挂载或安装该公开 CA；不得分发证书私钥。

共用 Nginx 仅在 ontology 站点补充 `172.17.0.1:443` Docker 网关监听及精确 Host 检查。原 loopback 入口保持；网关监听供本机容器访问，不增加 LAN 地址绑定。认证、租户范围、Origin、CSRF 与 MCP 令牌校验继续执行；TLS 和代理来源校验不能代替业务身份校验。

共用配置的仓库源文件和 WSL 生效副本均已更新。先以 `ontology-nginx-check` 容器校验，再在既有容器执行 `nginx -t` 和 reload。保留了其他 server 块、原 SSO issuer 和兼容入口。

## 本次已执行验证

| 层级 | 实际结果 |
| --- | --- |
| 服务测试 | 显式连接原本机 Fuseki，`124 passed, 1 skipped`；新 HTTPS 测试先失败再通过 |
| 发布工作树 | 新增的重建保留、升级目录隔离、篡改拒绝与构建输入范围测试均通过 |
| 镜像 | 固定 Node/Python 基础镜像摘要，uv locked 安装；前端构建通过，镜像内双方 schema 及依赖摘要校验通过 |
| Compose | 多文件组合 `config --quiet` 通过，两个运行容器的 project/service 标签符合设计 |
| HTTPS/API | Windows Python 客户端显式验证公开 CA，34 项检查通过，应用重建后再次通过 |
| 三类身份 | 原平台、甲方、乙方账号 HTTPS 登录/退出、Secure/HttpOnly/SameSite Cookie、会话注销通过 |
| 企业/API/MCP | 发布版本及双方 v1 schema 保留；真实外企业条目拒绝、错误 Origin 拒绝、双方 MCP tools/list 成功、匿名 MCP 拒绝 |
| Docker 网络客户端 | 严格 CA 的页面/health、错误 Host、非可信 peer 伪造 HTTPS scheme 拒绝、代理覆盖外来 scheme 共 5 项通过 |
| 容器重建 | 真实 force-recreate 应用后，账号/版本及新 Git 草案保留；验证用合成工作树随后清理 |
| 数据卷 | 新旧 Fuseki 卷名相同，旧容器停止，没有双进程打开同一卷 |
| 共用系统 | 其余 40 个容器 ID、镜像及按目标路径排序后的挂载保持；SSO Discovery issuer 仍为 `https://sso.lvh.me:8443`；Portal、小采、Octop 既有页面/health 均为 200 |
| 独立代码审阅 | 未发现 Critical/Important；记录一项 Minor：公开 Origin 的非法端口及显式默认端口配置可更早校验 |

私有运行证据位于 `ontology/evidence/`，不包含明文会话或模型密钥。比较 Docker inspect 挂载时按目标路径排序，避免数组顺序变化产生假阳性。

## 边界与回退

- 本次没有发送真实模型请求，也未执行新材料抽取、审核发布或 UAT 部署；上述 HTTP 成功不代表这些业务验收通过。
- Windows `curl.exe` 的 Schannel 默认吊销检查因本地 CA 无可用吊销信息返回 `CRYPT_E_NO_REVOCATION_CHECK`；没有关闭吊销检查或绕过浏览器警告。Windows Python、原生 WSL 和 Docker 客户端均通过显式 CA 的证书链/主机名校验；本轮未执行浏览器交互验收。
- 当前精确 Origin `https://ontology.lvh.me` 正常。非法端口/显式默认端口配置的提前校验为已记录 Minor；UAT 配置需按实际域名精确填写。
- 回退须先停止新应用和新 Fuseki，再启动原 Fuseki；保留新旧 SQLite 的最新性边界。新应用已有写入时，不能直接启用过期 Windows SQLite，应维护窗口双库备份并按恢复流程处理。禁止同时运行两套服务写同一前缀。
