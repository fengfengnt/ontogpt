# 采购本体工作台 SSO 登录设计

日期：2026-11-04。用户已选择方案 A，并明确授权直接设计、出计划和实现，无需再次确认。client ID、client secret 后续由用户通过私有配置提供；真实 SSO 登录验收须待凭据就绪。

## 意图与用户确认

- 普通用户通过已有 SSO 平台登录本工作台。
- SSO 用户首次登录不自动归属企业；超级管理员另行分配企业空间，默认成为该企业的 `company_admin`。
- 超级管理员继续使用现有本地用户名和密码。
- `/login/password` 是所有已有本地账号通用的密码登录入口，不限制为超级管理员。
- 保留既有账号、密码、会话协议、企业知识和企业权限边界。

## Approaches

- **A，后端接入 OIDC，用户已选择。** 后端交换授权码并验证身份，复用现有本地会话和企业授权；client secret 不进入浏览器。最适合现有 FastAPI、SQLite 和同源 React 工作台。
- B，前端公开客户端接入。浏览器执行 PKCE，后端另外验证其令牌并关联业务身份，需要调整更多鉴权边界，也不使用用户计划提供的保密客户端密钥。本次不采用。

## 当前约束与证据

- `identity.py` 中 `accounts` 必须已经绑定平台角色或企业角色，不能把待分配用户塞成 `company_id=NULL`，否则现有逻辑可能把空企业解释为平台范围。
- `create_account` 禁止平台管理员向已就绪企业注入本地账号。保留该限制，为待分配 SSO 身份增加单独的、可审计的分配操作。
- 后端已有随机会话、摘要存储、角色校验和同源写请求保护。前端从 `/v1/me` 获取身份。
- `httpx` 已是直接依赖；锁文件已有 `PyJWT[crypto]`，签名验证复用该库并将其声明为直接依赖，不自己实现 JWT 密码算法。
- 初次严格 TLS Discovery 的历史 issuer 为 `https://sso.lvh.me:8443`。同日中心已按用户指令切至 `https://sso.lvh.me`，且不再兼容旧 8443；现行配置及验证以 [443 切换记录](../../procurement-ontology/sso-issuer-443-2026-11-04.md) 为准，部署时重新核对。
- 认证源 UserInfo 当前仅提供 `sub,preferred_username,tenant_id`。`tenant_id`、client 的 `ownerTenantId` 均不决定本体企业空间。
- 当前 HTTPS 部署另有设计，本功能不替换共用 Nginx 或启动、迁移其他服务。SSO 真实接入依赖本工作台 HTTPS 与 CA 信任就绪。

## 登录入口与用户体验

- `/` 未登录时展示 SSO 登录入口及密码登录链接；不自动循环跳转 SSO。
- `/login/password` 直接展示现有用户名密码表单；成功后导航 `/` 并按原角色进入工作区。直接访问及刷新该路径均可用。
- SSO 尚未配置完整时显示“SSO 尚未配置”，密码登录仍可使用；不允许缺失凭据时静默降级为未校验身份。
- 待分配用户只看到等待分配说明、刷新分配状态和退出按钮，无企业菜单或企业数据。
- 平台工作区新增“SSO 用户分配”，展示已经成功通过 SSO 的身份及分配状态，从已就绪企业中选择目标并确认分配。平台管理员可以给已有管理员的企业分配额外 SSO 管理员，但不能因此浏览企业业务数据。

## 身份数据与授权

- 在同一 SQLite 管理库增加 SSO 身份、待分配会话、OIDC 登录事务和分配审计记录；不改写已有账号和外键。
- 外部身份以精确的 `(issuer, sub)` 唯一识别，`sub` 按不透明字符串保存，不自行解析；`preferred_username` 只是显示资料，不作为绑定键。首次并发登录只生成一份记录。
- 待分配身份没有本地 `account_id`，不能转换为 `Identity`，不能签发普通会话或 MCP 服务令牌。
- 分配时在一个 SQLite 事务中校验操作人为 `platform_admin`、目标企业为 `READY`、外部身份尚未分配；创建独立 `company_admin` 账号、绑定外部身份并记录审计。该账号使用内部生成的唯一用户名及不可验证的密码标记，不生成或交付本地密码；现有密码验证器会拒绝此标记。
- 同一身份向同一企业重复分配返回原结果，不重复创建账号或审计；已分配身份向不同企业分配返回 409。
- 已有本地账号与新 SSO 身份不按用户名、手机号或邮箱自动合并。首期不新增账号绑定、转企业、角色选择或 SSO 密码设置。
- 待分配会话在管理员分配后仍不能直接访问业务接口；用户同源 POST 激活，后端重新确认分配、账号有效性和企业就绪状态，再签发正常会话并撤销待分配会话。已分配用户再次 SSO 登录直接进入对应企业。

## OIDC 过程与安全边界

1. 后端从固定 HTTPS issuer 读取 Discovery，并要求返回 issuer 精确匹配；协议端点必须是该 issuer 的 HTTPS origin，禁止通过任意 URL 或重定向获取服务端资源。
2. 后端生成随机 state、nonce、PKCE verifier 和独立浏览器绑定值。事务 5 分钟有效，SQLite 保存 state/绑定值摘要及交换所需 nonce/verifier；浏览器绑定 Cookie 为 HttpOnly、Secure、SameSite=Lax，Path 固定在认证路由。
3. 使用 `response_type=code`、`scope=openid profile`、S256 和明确登记的回调 URI 顶层导航到认证中心。回调 URI 不从 Host/Forwarded 推导。
4. 回调只接受单值参数，state 必须匹配该浏览器、未过期、未消费的事务；先原子消费后换码，重放或失败均从新登录重新开始。
5. 后端用 HTTP Basic 的 confidential client 认证和 verifier 换码；校验 ID Token 的受支持非对称签名、issuer、audience/azp、exp、iat、nonce、非空 sub，以及认证源要求的 auth_time 类型与合理时间边界。通过服务器固定 JWKS 取公钥，不接受令牌给出的 jku/x5u。UserInfo 使用 access_token，返回的 sub 必须与 ID Token 相同。
6. 只有上述校验全部成功，才查找/创建外部身份并建立待分配会话或普通会话。access/refresh/id token 不返回给前端，不长期保存；不请求 refresh token。
7. 回调完成后 303 到不带 code/state 的本工作台地址；响应 no-store，日志不输出回调 query、Cookie、授权码、令牌、密钥或完整 UserInfo。

正式 HTTPS 的普通/待分配 Cookie 均启用 Secure、HttpOnly、SameSite=Strict；普通本地 HTTP 开发保持原密码登录可用，SSO 协议仅接受 HTTPS。Origin/CSRF 检查覆盖分配、激活、退出和密码登录，不对 callback 放开通用写接口。退出清理当前工作台普通会话与待分配会话，不注销其他设备或中心会话。

## 接口约定

| 接口 | 作用与限制 |
| --- | --- |
| GET `/v1/auth/sso/config` | 仅返回是否配置完整，不返回密钥 |
| GET `/v1/auth/sso/start` | 建立登录事务，设置浏览器绑定 Cookie 后跳转 |
| GET `/v1/auth/sso/callback` | 完成协议校验，建立工作台会话后 303；失败仅返回安全错误 |
| GET `/v1/me` | 保留正常身份字段；待分配返回 `status=PENDING_ASSIGNMENT`、`account_id/scope_id/role=null`；未登录 401 |
| POST `/v1/session/activate` | 仅有效待分配会话可激活已分配身份，未分配时 409 |
| POST/DELETE `/v1/session` | 保留密码登录；退出也支持待分配会话并清理两类会话 |
| GET `/v1/platform/sso-users` | 仅平台管理员可见的身份与分配状态列表 |
| GET `/v1/platform/companies` | 仅平台管理员，返回已就绪企业标识，不读取企业知识 |
| POST `/v1/platform/sso-users/{id}/assignment` | 仅平台管理员；body 仅 `company_id`，不允许传入角色或目标账号 |

前端等待状态不得作为授权手段。现有所有业务路由与 MCP 仍通过正常 `Identity` 校验，待分配 Cookie 永远不能被当作业务令牌。

## 配置、迁移和回退

私有运行环境新增 `PROCUREMENT_SSO_ISSUER`、`PROCUREMENT_SSO_CLIENT_ID`、`PROCUREMENT_SSO_CLIENT_SECRET`、`PROCUREMENT_SSO_REDIRECT_URI`。本地规划回调为 `https://ontology.lvh.me/v1/auth/sso/callback`；生产/UAT 独立登记，不复制本地密钥。空配置不影响密码登录，部分配置拒绝启用 SSO。尚未提供真实 client 凭据，不创建替代凭据或修改认证源登记。

所有新表通过现有初始化进行增量创建；既有表不 DROP、不重建。SSO 内部账号保持现有 accounts 约束。管理库备份包含上述记录，恢复后已过期事务/会话不能复活。迁移前后核对已有账号、企业状态和业务版本；回退代码保留新表，不删除企业数据。若新账号已写入，旧版本仍不能验证其密码标记。

## 本次不做与已知边界

- 一个 SSO 用户首期分配到一个企业；不新增组织模型、多企业切换、账号自动合并或权限同步。
- 不实现中心全局退出、back-channel logout、在线 token introspection 或自动刷新。工作台会话沿用 1 小时有效期，SSO 中心停用或退出不会即时撤销已经签发的工作台会话；本地账号有效性和企业状态仍每次检查。
- 本次不部署共用基础设施，不发送短信，不修改认证源、Portal、AI 或 New API。

## 验收标准

1. 真实 SQLite：既有账号/密码/企业关系保留；同一外部身份并发或重复登录不重复创建；分配原子且可审计，普通企业管理员/reader 无权分配。
2. HTTP：完整模拟协议使用真实签名 JWT、PKCE 和 HTTP transport，覆盖成功/等待/分配/激活/退出，以及错误 state、其他浏览器、过期/重放、nonce/签名/iss/aud/sub 不匹配、坏 Discovery/JWKS、网络失败与缺少配置。
3. 权限：待分配用户不能读写企业、平台或获取 MCP 令牌；激活后仅进入被分配企业；原平台不能浏览企业知识的限制保留。
4. 前端：SSO 入口、通用密码路径、待分配刷新、管理员分配、错误/忙碌状态通过测试，构建成功；后端直接刷新密码路径可返回页面。
5. 回归：采购服务测试与前端测试通过；原 OntoGPT Web 演示不变。
6. 真实 HTTPS Discovery 已检查；真实 client 登录、短信、真实浏览器跨站 Cookie 和部署验证待凭据及部署就绪后执行，不用模拟测试替代。

## 实施者决定与依据

本设计由实施者选择：不自动合并账号、只允许首次分配、工作台本地退出、保留一小时会话、复用现有 JWT 库、显式列举密码路由而不添加全站 SPA fallback。以上没有被描述为用户先前指定的要求。

源码范围：`services/procurement_ontology/procurement_ontology/{identity,api,runtime}.py`、新增 SSO 协议模块、服务依赖声明与锁文件；`frontend/procurement-ontology/src/{App,api}.tsx/ts` 及必要的登录/分配组件、样式和测试。具体内部函数、表名和小范围拆分由实施者决定，不能扩大权限。

参考：[OIDC Core 授权码流程](https://openid.net/specs/openid-connect-core-1_0.html#CodeFlowAuth)；认证源当前接入契约为配套 SSO 工程 `docs/sso/backend-integration.md`。身份状态、Cookie 和令牌以当前协议契约为准。
