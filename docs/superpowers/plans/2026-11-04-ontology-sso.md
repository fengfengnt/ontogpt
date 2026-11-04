# 采购本体 SSO 登录实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. 用户已授权连续设计、计划与实现，无需中途确认。

**Goal:** 后端 OIDC 登录、待分配 SSO 用户、超级管理员分配企业及通用密码登录入口形成完整闭环。

**Architecture:** SQLite 管理外部身份和登录事务，后端换码验签后复用现有企业身份与会话。待分配会话与正常业务会话隔离。前端复用现有工作区和表单样式。

**Tech Stack:** Python/FastAPI、SQLite、httpx、PyJWT[crypto]、React/TypeScript、pytest、Vitest。

**Spec:** `docs/superpowers/specs/2026-11-04-ontology-sso-design.md`

## Global Constraints

- 保留所有既有账号和企业数据，不按同名/手机号合并。
- 分配后角色固定 `company_admin`，仅 `platform_admin` 可执行分配；只支持首次分配。
- `/login/password` 允许所有既有本地账号；SSO secret 只进私有后端配置。
- SSO 未配置时密码登录仍可用；未有真实凭据前不宣称真实登录通过。
- 修改仅限采购本体服务、前端和相关文档/测试；不触碰原 Web 演示和其他工程部署。

## Review Focus

- 待分配身份空企业绝不被解释为 platform；身份及业务 Token 的边界由任务 1/3 测试固定。
- 同一外部身份并发登录和重复分配不能创建两个账号；事务行为由任务 1 测试固定。
- 跨站回调 Cookie 与普通 Strict 会话互不替代；其他浏览器 state、重放由任务 2/3 测试固定。
- 企业已就绪但已有管理员时允许分配 SSO 身份，原本地注入仍禁止；任务 1/3 验证。
- 已有平台密码会话不能因 SSO 未配置而被锁出，密码路径直接刷新不能 404；任务 3/4 验证。

### Task 1: 外部身份和原子企业分配

**Files:** 修改 `services/procurement_ontology/procurement_ontology/identity.py`；新增 `services/procurement_ontology/tests/unit/test_sso_identity.py`。

**Interfaces:** IdentityStore 提供 `sso_user(issuer, sub, username)`、`list_sso_users(actor)`、`assign_sso_user(user_id, company_id, actor)`、`issue_pending_session(user_id)`、`pending_user(token)`、`activate_pending(token)`、`revoke_pending_session(token)`；正常返回现有 `Identity`，待分配返回资料而非 Identity。

- [ ] 写真实 SQLite 测试：身份唯一、不自动合并、平台分配到 READY 企业、幂等/冲突、越权拒绝、待分配无业务权限及激活后撤销旧 Cookie。
- [ ] 运行新测试确认缺失行为导致失败。
- [ ] 实现增量表与事务，保留原账号约束和密码认证限制；分配记录随管理库备份。
- [ ] 运行 `pytest tests/unit/test_identity.py tests/unit/test_sso_identity.py -q`，预期全通过；提交。

### Task 2: 后端 OIDC 协议

**Files:** 新增 `services/procurement_ontology/procurement_ontology/sso.py`、`services/procurement_ontology/tests/unit/test_sso.py`；修改服务 `pyproject.toml`、`uv.lock`。

**Interfaces:** `SSOConfig.from_env()` 返回完整配置或 None；`SSOClient.start()` 生成服务端事务和浏览器绑定；`SSOClient.finish(state, binding, code)` 返回经过验证的 issuer/sub/username。消费事务与浏览器绑定由该模块负责，身份分配留给 Task 1。

- [ ] 使用真实 RSA 签名和 httpx MockTransport 写协议测试，固定请求参数、Basic 认证、UserInfo 对齐以及签名/nonce/issuer/audience、重放/过期、错误元数据失败拒绝。
- [ ] 运行新测试确认失败。
- [ ] 用 httpx 与 PyJWT 实现 HTTPS Discovery/JWKS、授权码和 S256，事务 5 分钟、一次消费；禁止端点任意跳转和泄漏凭据。
- [ ] 运行 `pytest tests/unit/test_sso.py -q`，预期全通过；提交。

### Task 3: HTTP 登录、分配和会话闭环

**Files:** 修改 `api.py`、`runtime.py`；新增 `tests/unit/test_sso_api.py`；保留并扩展现有 API 测试。

**Interfaces:** 实现设计中的 `/v1/auth/sso/*`、待分配 `/v1/me`、`POST /v1/session/activate`、待分配退出和平台用户/企业列表及分配接口；`create_app(..., sso_config=None)` 支持明确注入配置，runtime 从私有环境加载。

- [ ] 先写 HTTP 测试：SSO 未配置不影响密码、待分配不能读写业务/平台/MCP、平台分配与用户激活、错误 Origin/CSRF、路径刷新。
- [ ] 运行新测试确认失败。
- [ ] 注册固定路由并处理安全 Cookie、no-store、安全协议错误；保留现有鉴权与 MCP 路径；密码登录清除待分配状态，退出撤销当前两种会话。
- [ ] 运行 `pytest tests/unit -q`，预期无失败；提交。

### Task 4: 登录与分配界面

**Files:** 修改 `frontend/procurement-ontology/src/{App.tsx,api.ts,App.test.tsx}`；必要时新增 `LoginPages.tsx` 及其测试，复用现有样式。

**Interfaces:** `/v1/me` 的待分配响应由前端单独处理；平台新增 SSO 分配菜单，使用 Task 3 固定 API；密码登录链接固定 `/login/password`。

- [ ] 写前端测试，覆盖密码路径、默认 SSO、未配置、待分配刷新、管理员选择企业/提交和错误态；先运行确认失败。
- [ ] 实现最小组件和路径切换，分配角色固定，不新增 router 依赖。
- [ ] 运行 `npm test -- --run` 和 `npm run build`，预期通过；提交。

### Task 5: 回归、独立审查与交付

**Files:** 更新服务 README、设计/本计划；保存独立审查结果和实际验收边界。

**Interfaces:** 文档列出四个配置键、精确 callback、密码 URL，以及没有凭据时的限制。

- [ ] 运行采购服务测试、前端全测试/构建、`git diff --check`；对实际外部依赖测试区分可运行与缺少环境的情况。
- [ ] 按 requesting-code-review 技能派独立审阅者检查完整变更，处理真实安全或行为问题并补回归测试。
- [ ] 用服务端页面测试确认密码 URL 可直接刷新；不冒充真实 SSO 浏览器验收，不启动或重建共用服务。
- [ ] 更新任务与验收结果并提交，保留可审阅隔离工作区；不推送远端。
