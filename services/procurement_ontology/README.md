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

## 模型配置

在启动服务的进程环境中配置，或写入运行目录自己的 `.env`；也可以通过 `PROCUREMENT_ENV_FILE` 指定现有配置文件。不要将密钥提交 Git 或发到聊天中。

```text
PROCUREMENT_MODEL=deepseek/deepseek-flash
PROCUREMENT_API_BASE=https://api.deepseek.com
PROCUREMENT_MAX_OUTPUT_TOKENS=16384
```

`PROCUREMENT_API_KEY` 为可选的显式密钥变量；缺省时复用现有 `LLMClient` 的提供方凭据解析，包括 Oaklib 的 `deepseek-key`。模型名称和服务地址须与实际提供方一致。模型提取、缺口起草和 Agent 均通过服务客户端调用，关闭材料缓存与提示正文日志。

## 审核、发布与 schema 激活

1. 企业保存原文并运行模型提取，保留来源修订、模拟标记、schema 版本和摘要。
2. 审核候选；无可定位原文的建议不能直接采纳。同项目、同阶段、同口径的成本冲突需要显式处理。
3. 树菜单或画布修改只保存为待审批次。核对来源与差异后发布完整新版本；旧基础版本返回 `409`。
4. Schema 缺口生成独立 `codex/schema-draft/` 工作树中的新版本 YAML/Python。人工 Git 审阅、生成一致性和业务回归测试通过后，部署新产物及摘要注册项。
5. 审核人使用本企业管理会话执行下列命令；部署本身不会切换启用版本。

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
uv run --project services/procurement_ontology procurement-service restore 'D:/Backups/procurement/2026-10-20/manifest.json' --destination 'D:/ProcurementRuntime/restored-20261020' --dataset-prefix procurement_restore_20261020_
```

备份目录必须尚不存在。备份包含 SQLite 和本项目前缀下的全部 Fuseki 数据集，以 N-Quads 保留默认图和具名图；记录 SHA-256、当前版本和部署注册表，最后才写 `manifest.json`。具体四元组协议见 [Jena 官方说明](https://jena.apache.org/documentation/fuseki2/fuseki-config-endpoint)。

恢复先核验所有文件、SQLite 完整性和已部署 schema 摘要，再导入**空运行目标和空数据集前缀**。不会覆盖当前库或其他服务卷。逐图核对 RDF 等价性和当前指针后才生成完成记录；中途失败留下 `restore.incomplete`，服务拒绝启动该目标。失败目标保留供检查，重试使用另一个空目标。

完成后设置以下环境变量，再启动恢复目标：

```powershell
$env:PROCUREMENT_RUNTIME_DIR = 'D:/ProcurementRuntime/restored-20261020'
$env:PROCUREMENT_DATASET_PREFIX = 'procurement_restore_20261020_'
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
