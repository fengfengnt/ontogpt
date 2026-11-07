# Ontology 本地 WSL 镜像与共用 HTTPS 部署设计

日期：2026-11-04。状态：用户以“实施”批准，已完成本地部署；实际证据及未执行范围见 `docs/procurement-ontology/deployment-2026-11-04.md`。

## 意图与已确认约束

将采购本体知识服务部署到本机 Ubuntu WSL Docker，通过既有共用 HTTPS 入口供 Windows 浏览器与本机 WSL 系统调试；产出以后可在 UAT 使用的应用镜像及部署配置。

- 用户指定 Compose 项目名 `yunhezhiyuan`，本项目全部容器名以 `ontology-` 开头。
- 用户已选择复用现有 `yunhezhiyuan-nginx`，不新增本项目代理容器。
- 沿用已规划入口 `https://ontology.lvh.me/` 与宿主上游 `127.0.0.1:8002`。
- UAT 域名规划为 `ontology-uat.yuhezhiyuan.com`，本次不部署 UAT、不变更真实 DNS。
- 共用代理、证书及全站域名记录以用户转交文档引用的 SSO 工程部署记录为权威；本文件只记录 ontology 的接入约定。

## 当前证据

- `deploy/fuseki/compose.yaml` 只管理 Fuseki。实际容器为 `procurement-ontology-fuseki-1`，镜像 `procurement-fuseki:6.2.0`，宿主端口 `127.0.0.1:3032`。
- Fuseki 业务卷为 `procurement-ontology_fuseki_data`；当前 Shiro 从本仓库私有 runtime 路径只读挂载。
- 应用当前以本地 Python 运行，`serve` 固定监听 loopback、一个 worker；网页构建由同一应用提供。当前未发现 8002 应用监听。
- 身份、会话与 schema 启用指针位于 `services/procurement_ontology/runtime/control.sqlite3`，知识及业务版本位于 Fuseki/TDB2。
- 实际共用 Nginx 使用 host 网络；`ontology.lvh.me:443` 已转发 8002，并设置 Host 和 HTTPS 转发头。
- MCP Host/Origin 目前只允许本机 HTTP；管理接口检查 Origin；会话 Cookie 未设置 Secure。
- 自动 schema 草案通过 `git worktree add` 生成，依赖本地 Git 仓库和仓库之外的草案目录。
- 本次 `git worktree list` 发现 10 个已有 schema 草案工作树；严格验证既有 CA 的 ontology HTTPS 请求返回 502，与上游未监听一致。

## Approaches

| 方案 | 优点与代价 | 结论 |
| --- | --- | --- |
| A：本项目另建代理容器和独立 HTTPS 端口 | 配置独立；增加入口、证书管理与端口 | 未选择 |
| B：复用现有共用 Nginx、既定域名和 8002 上游 | 符合用户已有多应用规划；必须精确维护共用配置与发布边界 | 用户已选择 |

以下镜像、持久化和验证细节为本设计建议，待用户审阅。

## 服务与网络

- Compose 服务键使用 `ontology-app`、`ontology-fuseki`，容器分别命名为同名；避免与共用组已有 `backend`、`nginx` 服务键冲突。
- 一次性构建验证、迁移或探测容器也显式使用 `ontology-` 前缀，不能依赖 Compose 自动生成名称。
- 在本仓库维护 ontology 专属 Compose 片段，通过明确的多文件组合命令加入现有 `yunhezhiyuan` 项目。部署、启动和停止均显式指明 ontology 服务，不使用删除 orphan 的选项。
- 实际部署目录建议为 `/home/fengfeng/yunhezhiyuan/ontology/`，包含版本化镜像引用、专属配置、私有运行目录及草案。此目录是本设计建议，不替代全站权威记录。
- 应用容器内监听 `0.0.0.0:8002`，仅映射宿主 `127.0.0.1:8002`；保持一个 worker 与现有运行目录锁。
- Fuseki 保留宿主 `127.0.0.1:3032`；应用经 ontology 专属 bridge 网络访问 `http://ontology-fuseki:3030`。不把业务应用加入 Java 数据库网络。
- 既有共享代理继续终止 TLS，网页、API、MCP 使用同一 `https://ontology.lvh.me` Origin。
- Windows 和原生 WSL 调用沿用本地域名及既有 CA。Docker 调用方不得把容器自身 localhost 当作入口：按实际网络将域名解析到宿主网关，在 ontology 站点增加必要的网关监听及入口限制，并用一个真实 Docker 网络客户端验证；不变更 SSO internal 规则或其他站点监听。
- CA 只分发公开的 `certs/local-ca.pem`；私钥仅由现有代理持有。所有请求验证证书链和主机名，不使用 `verify=false` 或 `curl -k` 作为验收。

## 镜像与 schema 草案

- 构建应用镜像，打包 Python 依赖、后端、构建后的前端、模板与 schema 注册表；固定可追溯的源码版本和构建摘要。
- 采用显式最小构建上下文，排除 `.env`、运行库、服务令牌、模型凭据、CA 私钥、宿主 `.git`、临时文件和未审核草案。现有未提交的旧 Web 演示改动不自动进入采购服务发布。
- 镜像包含 Git 程序，以及从审核后源码初始化的无远端凭据本地 Git 基线，不复制宿主完整 Git 历史。
- 为保持当前 worktree 功能，使用按镜像发布标识隔离的持久工作目录：首次启动从镜像种子初始化干净仓库，核对发布摘要，再从该仓库加载应用、模板和注册表。草案 worktree 放在其外的持久目录。
- 重建相同版本容器继续使用原仓库和草案；升级镜像初始化新发布仓库，不覆盖旧工作树。运行源码、依赖导入路径、模板及前端产物须与当前镜像发布标识一致，不允许旧卷遮蔽升级代码。
- 自动草案仍需人工 Git 审阅、测试、构建部署和显式激活；运行容器不自动推送、合并或发布 schema。
- 现有 Windows 草案不直接复制其含绝对路径的 `.git` 引用到 Linux。迁移前逐个保存相关已提交分支、未提交差异和新增文件，记录 gap ID、基线版本与原路径，并保留原工作树供人工审阅；既有草案记录保留原始元数据，新草案在 Linux 发布仓库生成。本次不自动重新生成或激活旧草案。
- UAT 使用同一构建产物，外置域名、代理、凭据和数据路径；本次不承诺多实例并行写入或高可用。

## HTTPS 与认证适配

- 将监听地址、公开 Origin、可信代理来源及 MCP Host/Origin 改为显式部署配置；本机原 HTTP 启动方式保留可用。
- 应用只接受实测的 Nginx 到应用连接来源作为可信代理，不使用 `*` 或信任整个 Docker 网段。共用 Nginx 覆盖转发头。host 网络代理与其他本机进程可能共享同一上游 peer，因此仅靠 IP 不能区分二者；本地受信进程属于本次调试信任边界，不承诺防御本机管理员伪造转发头。其他网络来源的转发头不受信，业务身份始终独立校验。
- HTTPS 部署会话 Cookie 设置 Secure、HttpOnly、SameSite=Strict；退出时匹配对应 Cookie 属性。
- 管理写接口继续校验精确同源 Origin 和原有 CSRF 标记；MCP 继续执行企业绑定服务令牌与 Host/Origin 检查。
- 新域名接入不构成统一 SSO 登录集成。本次继续使用采购服务现有身份与会话。
- 长时间模型请求、MCP 和流式请求核对代理超时及缓冲行为；优先沿用现有 ontology server 块，只在实际验证发现缺项时局部调整。

## 数据迁移、配置与回退

- 先确认本项目无运行中的旧写入者，执行现有双库备份并保存版本、数量/摘要、启用 schema 和挂载基线；备份失败则不切换。
- 将 SQLite 与必要私有运行文件安全复制到 WSL 新运行目录，核对完整性、账号/schema 状态及文件权限；不重新 bootstrap 已有管理员，不重新初始化企业。
- 迁移时逐项适配 Windows 路径、容器内凭据路径、Fuseki 服务地址和草案目录，保留原数据集前缀及已有启用版本；不能原样套用私有环境文件中的宿主绝对路径。
- 保留并显式引用现有 Fuseki 卷为 external volume。迁组前停止旧 Fuseki；新 `ontology-fuseki` 使用同一卷及既有 Shiro 凭据启动，禁止两个进程同时打开同一 TDB2 卷。
- 旧容器在新服务验证期间保持停止而可回退；停止服务不删除卷。回退顺序为停止新应用和新 Fuseki，恢复旧 Fuseki；若新应用已有写入，则使用同一最新数据/经核验的双库恢复，不能简单切回过期 SQLite 副本。
- 明确迁移后的唯一活动运行目录与管理/备份入口；旧目录保留为回退副本，不启动第二个服务并行写入。
- 模型配置通过私有部署环境文件加载；Fuseki 凭据文件只读挂载。复用已有凭据，不在命令行、日志、镜像和设计文档中记录正文。仅配置文件存在不代表真实模型调用成功。
- 共用配置需要修改时先备份、核对最新文件、保留其他 server 块，按权威文档校验并生效；禁止覆盖整份共用 Compose/Nginx 文件。
- 不改变现有 SSO issuer、回调、client 或 bridge secret；不重建 MySQL/Redis，不清理其他项目资源。

## 验证与完成标准

1. 源码：针对新增代理、Cookie、Origin 和部署配置的测试通过，前端构建通过，原认证/企业范围行为保持。
2. 配置：组合后的 Compose 验证通过；仅 ontology 两个服务被创建/迁移，容器标签项目名和前缀符合用户要求。
3. 保留性：迁移前后 Fuseki 卷相同，SQLite 完整，关键业务/版本/schema 状态一致；共用组其他容器与挂载保持。
4. 严格 TLS：Windows、WSL、一个 Docker 网络客户端均能经正确 CA 访问 `https://ontology.lvh.me/` 及静态资源，MCP 匿名访问返回认证错误而非 502。
5. 认证：HTTPS 登录、Secure Cookie、同源写操作成功；错误 Origin、错误 Host、匿名/跨企业访问被拒绝；不受信 peer 不能凭伪造代理头改变来源协议判断。凭据经私有文件读取，不打印会话或令牌。
6. 持久性：重建应用容器后账号、版本、schema 与 Git 草案仍可用；切换发布版本不会加载旧应用文件。
7. 共用入口回归：至少核对 SSO Discovery 仍使用既有 issuer、Portal 静态及其他既有就绪站点未受影响；未就绪站点不记为业务通过。
8. 模型调用、实际抽取审核发布与 UAT 验收分别记录，未执行明确标注；页面 200 不替代这些结果。

## 实施者可决定事项

基础镜像和运行 UID、镜像标签格式、具体构建/入口脚本拆分、发布工作目录初始化实现及测试夹具由实施者选择，要求满足上述数据保留、镜像可追溯和身份边界。若发现现有凭据无法读取或关键草案只能依赖未提交文件，应保留现场并明确列出所需输入，不生成替代账户或丢弃草案。
