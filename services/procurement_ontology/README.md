# 采购本体知识服务 MVP

独立于原有 OntoGPT Web 演示。业务知识保存在 Fuseki/TDB2，SQLite 保存账号、会话及企业品类的启用 schema 指针。平台管理通用模板，企业只能访问各自独立实例。

设计与评审入口：[文档索引](../../docs/procurement-ontology/README.md)。实施记录：[当前计划](../../docs/superpowers/plans/2026-10-19-procurement-ontology-mvp.md)。

## 本机启动

在工程根目录使用 Windows PowerShell；需要 Python、uv、Node.js，以及已启动的 WSL Fuseki。Fuseki 部署步骤见 [部署说明](../../deploy/fuseki/README.md)，本项目端口为 `127.0.0.1:3032`。

```powershell
uv sync --project services/procurement_ontology
npm ci --prefix frontend/procurement-ontology
npm run build --prefix frontend/procurement-ontology
uv run --project services/procurement_ontology procurement-service bootstrap-admin --username platform
uv run --project services/procurement_ontology procurement-service serve --port 8002
```

首次初始化命令交互输入密码，不回显。浏览器访问 `http://127.0.0.1:8002`，由平台入口初始化 `test_buyer1` 和 `test_supplier1`，分别创建首个企业管理员。企业开通会复制当时的通用本体和三级树；旧企业不会随后同步。平台不能进入企业业务数据。

默认运行目录为 `services/procurement_ontology/runtime/`，已经排除 Git。`PROCUREMENT_RUNTIME_DIR` 可以指定另一个本机目录。服务仅监听本机，使用一个进程；同一个数据集前缀只允许配给一个运行目录和服务实例。

## SSO 与密码登录

默认首页提供 SSO 登录；所有已有本地账号，包括平台管理员、企业管理员和只读用户，都可以直接通过 `/login/password` 使用用户名和密码登录。按上面的本机启动方式，密码入口为 `http://127.0.0.1:8002/login/password`。SSO 未配置时仍保留该入口。

SSO 使用后端 OIDC 授权码流程，client secret 只保存在后端私有运行环境或运行目录 `.env` 中。配置完整后重启本服务生效：

| 配置键 | 内容 |
| --- | --- |
| `PROCUREMENT_SSO_ISSUER` | 认证源当前固定 HTTPS issuer；本地本轮核对值为 `https://sso.lvh.me:8443`，切换 443 后须重新核对，不能由请求域名推测 |
| `PROCUREMENT_SSO_CLIENT_ID` | SSO 管理后台登记的 confidential client ID |
| `PROCUREMENT_SSO_CLIENT_SECRET` | 该 client 的密钥，仅写入私有配置，不提交 Git、不发到聊天中 |
| `PROCUREMENT_SSO_REDIRECT_URI` | SSO 后台精确登记的 HTTPS 回调，路径固定 `/v1/auth/sso/callback` |

本地 HTTPS 规划为 `https://ontology.lvh.me/`，对应回调 `https://ontology.lvh.me/v1/auth/sso/callback`、密码入口 `https://ontology.lvh.me/login/password`。这些地址依赖另行部署的工作台和共用代理，本功能的代码完成不表示部署完成。SSO 发起和回调必须来自配置的 HTTPS origin。认证源为该 client 启用 `authorization_code`、`client_secret_basic`、`openid profile` 和 S256 PKCE。

HTTP 客户端使用 Python 系统默认 TLS 信任并校验证书，禁止关闭验证。自签本地 CA 需在实际运行宿主/容器中受信；也可通过 Python 支持的 `SSL_CERT_FILE` 指定可信公共 CA bundle，不能把私钥或应用密钥写入该文件。共用 Nginx/网关及日志采集必须屏蔽认证回调的 query，不能记录 code、state、Cookie、Authorization 或凭据正文；本服务启动命令默认 `log_level=warning`，不要为认证路径开启请求内容日志。

用户首次 SSO 登录仅建立待分配身份，不读写任何企业数据。平台管理员从密码入口登录，在“SSO 用户分配”中选择已就绪企业，用户随后点击“刷新分配状态”即可成为该企业的企业管理员。不会按同名、手机号或来源 `tenant_id` 关联既有账号，SSO 用户不会获得自动生成的本地密码。分配写入 SQLite 审计，重复分配同一企业不创建重复账号；首期不提供转企业或账号合并。

“退出登录”只退出本工作台，中心会话可能仍有效，之后 SSO 登录可能无需重新输入验证码。工作台会话有效期沿用一小时；中心退出或停用不即时撤销已签发的工作台会话。本地账号有效性和企业就绪状态仍在每次鉴权时核验。

协议测试使用模拟认证源和真实 RSA 验签；真实 client 凭据、浏览器跨站 Cookie 和 HTTPS 部署仍需单独联调。[设计与边界](../../docs/superpowers/specs/2026-11-04-ontology-sso-design.md)、[实施计划](../../docs/superpowers/plans/2026-11-04-ontology-sso.md)。

## 模型配置

在启动服务的进程环境中配置，或写入运行目录自己的 `.env`；也可以通过 `PROCUREMENT_ENV_FILE` 指定现有配置文件。不要将密钥提交 Git 或发到聊天中。

```text
PROCUREMENT_MODEL=deepseek/deepseek-flash
PROCUREMENT_API_BASE=https://api.deepseek.com
PROCUREMENT_MAX_OUTPUT_TOKENS=16384
```

`PROCUREMENT_API_KEY` 为可选的显式密钥变量；缺省时复用现有 `LLMClient` 的提供方凭据解析，包括 Oaklib 的 `deepseek-key`。模型名称和服务地址须与实际提供方一致。模型提取、缺口起草和 Agent 均通过服务客户端调用，关闭材料缓存与提示正文日志。

当前 DeepSeek 默认启用高强度 thinking；结构化任务显式使用 `reasoning_effort=none`，将输出预算用于 JSON。提供方默认行为见 [DeepSeek 官方说明](https://api-docs.deepseek.com/guides/thinking_mode/)。达到输出上限的运行标记失败，不接受截断候选；响应正文和结束原因保存在本企业未发布的运行记录中，供授权管理员核对，不进入普通查询或客户端缓存。

## 审核、发布与 schema 激活

1. 企业保存原文并运行模型提取，保留来源修订、模拟标记、schema 版本和摘要。
2. 审核候选；无可定位原文的建议不能直接采纳。同项目、同阶段、同口径的成本冲突需要显式处理。
3. 树菜单或画布修改只保存为待审批次。核对来源与差异后发布完整新版本；旧基础版本返回 `409`。
4. Schema 缺口生成独立 `codex/schema-draft/` 工作树中的新版本 YAML/Python。人工 Git 审阅、生成一致性和业务回归测试通过后，部署新产物及摘要注册项。
5. 审核人使用本企业管理会话执行下列命令；部署本身不会切换启用版本。

候选批次遇到 `409 STALE_BASE_VERSION` 时，在“候选审核”选择该批次，显式执行“按当前版本重新审核（清空旧决定）”。服务校验最新观察版本，保留旧审计并清空旧决定，须逐条重新审核；不会自动沿用旧决定或放宽冲突检查。三级树已绑定的二级品类键不能改绑到其他节点。

```powershell
$env:PROCUREMENT_ADMIN_TOKEN_FILE = '本机已保护的管理会话令牌文件路径'
uv run --project services/procurement_ontology activate-schema test_buyer1 computer v1
```

CLI 发送 Bearer 管理会话，不直接改 SQLite。管理会话通过 `POST /v1/session` 登录响应中的 `procurement_session` Cookie 取得，有效期一小时；编程客户端可以把该 Cookie 值保存到运行目录中的临时令牌文件，再交给 CLI。浏览器使用 HttpOnly、SameSite Cookie，管理写请求还检查同源标记和 Origin。SQLite 指针和操作者/时间审计同事务更新；正在提取的任务保留启动时版本。

MVP 没有岗位级条目过滤，`access_policy_ref` 保持 `null`。企业范围及基本管理员/查询权限已在服务执行。

## MCP 与问答

MCP 地址为 `http://127.0.0.1:8002/mcp/`，使用企业绑定的独立服务令牌（`POST /v1/manage/service-token`）。仅提供 `search_ontology_items`、`get_ontology_item`，不提供写工具或自由 SPARQL。

`test_buyer1` 的已授权读取账号可打开“本体问答测试”；乙方和平台不能调用固定甲方 Agent。LangGraph 流程为搜索、版本固定的详情读取、组织回答。无依据或模型引用未读过的 ID 时不输出事实答案；来源和模拟/项目范围由工具结果组装。

## 双备份与恢复

本地管理命令要求先停止对应运行目录的服务。文件锁拒绝与正在运行的服务同时操作；进程内的共享写入闸门也覆盖来源、提取、审核、发布、草案、SQLite 和 Fuseki 写入，先拒绝新写入，再等待在途操作完成。维护期间认证读取也可能暂时不可用。

```powershell
uv run --project services/procurement_ontology procurement-service backup --destination 'D:/Backups/procurement/2026-10-20'
uv run --project services/procurement_ontology procurement-service restore 'D:/Backups/procurement/2026-10-20/manifest.json' --destination 'D:/ProcurementRuntime/restored-20261020' --dataset-prefix restored20261020_
```

备份目录必须尚不存在。备份包含 SQLite 和本项目前缀下的全部 Fuseki 数据集，以 N-Quads 保留默认图和具名图；记录 SHA-256、当前版本和部署注册表，最后才写 `manifest.json`。具体四元组协议见 [Jena 官方说明](https://jena.apache.org/documentation/fuseki2/fuseki-config-endpoint)。

目标数据集前缀不能与备份源前缀相同或互为前缀，导入前即拒绝重叠配置。恢复先核验所有文件、SQLite 完整性和已部署 schema 摘要，再导入**空运行目标和空数据集前缀**。不会覆盖当前库或其他服务卷。逐图核对 RDF 等价性和当前指针后才生成完成记录；中途失败留下 `restore.incomplete`，服务拒绝启动该目标。失败目标保留供检查，重试使用另一个空目标。

完成后设置以下环境变量，再启动恢复目标：

```powershell
$env:PROCUREMENT_RUNTIME_DIR = 'D:/ProcurementRuntime/restored-20261020'
$env:PROCUREMENT_DATASET_PREFIX = 'restored20261020_'
uv run --project services/procurement_ontology procurement-service serve --port 8002
```

模型密钥、Fuseki 凭据和未提交的 schema 工作树文件不进入双库备份。先部署备份所需的 Git/schema 版本；待审草案的状态、来源和差异随 RDF 恢复，工作树文件须另外通过 Git 保存。该机制面向单进程本机 MVP，不支持多实例并行写入。

## 自动验证与证据边界

```powershell
$env:FUSEKI_TEST_URL = 'http://127.0.0.1:3032'
uv run --project services/procurement_ontology pytest services/procurement_ontology/tests -q
npm test --prefix frontend/procurement-ontology -- --run
npm run build --prefix frontend/procurement-ontology
git diff --check
```

集成测试为每次运行创建独立测试前缀并清理自己的数据集；没有显式 `FUSEKI_TEST_URL` 时真实存储测试会跳过。测试替身用于稳定验证模型边界，不代表提供方连接或业务事实已验收。真实模型、浏览器三类身份、重启和恢复须在贯通记录中单独列出结果。

## 本次实际验收

2026-10-20 已实际运行真实 DeepSeek 提取、三类身份浏览器操作、API/MCP 内容与版本比较、Docker 重启及 CLI 双库恢复。结果和边界见[本地技术验收记录](../../docs/procurement-ontology/acceptance-2026-10-20.md)。当前两家仍启用 v1；6 个 v2 草案仅在独立 Git 分支待人类审核。

失败的提取运行可显式重试：run ID 保持稳定，重试使用新的不可变候选批次，旧失败批次留存审计；已经成功或正在执行的运行重复请求直接返回，不重复调用模型。
