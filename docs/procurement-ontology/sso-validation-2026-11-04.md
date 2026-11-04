# SSO 登录实现与验证记录

日期：2026-11-04。结论：采购本体工作台的 SSO 接入代码、密码登录独立入口和企业分配闭环已实现；真实 client 凭据、实际浏览器登录和部署尚待完成。

## 交付范围

- 普通入口 `/` 提供 SSO；`/login/password` 为所有已有本地账号提供用户名密码登录。
- SSO 后端完成 confidential OIDC 授权码、S256 PKCE、浏览器绑定、一次消费和 RSA/JWKS 验签，令牌不返回前端。
- 新 SSO 身份无企业、无业务会话，不会被解释为平台角色；由现有本地超级管理员在“SSO 用户分配”中分配已就绪企业，角色固定为企业管理员。
- 分配后，待分配用户同源激活进入企业；已分配用户下次 SSO 登录直接进入工作区。
- 现有本地账号、密码验证、平台/企业隔离和禁止平台注入本地企业账号的规则保留。
- 只新增 SQLite 表，不重建既有表；本轮只操作测试临时库，没有迁移真实运行库。

首次交付位于本聊天附加的隔离工作区 `C:/Users/70367/.codex/worktrees/ontology-sso/ontogpt`。同日用户要求继续下一步后，已将 `codex/ontology-sso` 快进合并到 `D:/Code/ontogpt` 的 `main`，集成代码为 `cd991f1c`。主目录原有两处 Web 演示修改的 SHA256 和 107 个未跟踪文件的列表均核对保持；未推送远程、未启动或重建现有服务。

## 主目录集成复核

- 在 `D:/Code/ontogpt` 主目录重新执行完整服务测试：**102 passed，47 skipped**；前端 **18 passed**，TypeScript/Vite 构建通过，结果与隔离分支一致。
- 私有运行配置保留所有原字节和已有配置值，仅追加非秘密项 `PROCUREMENT_SSO_ISSUER=https://sso.lvh.me:8443`、`PROCUREMENT_SSO_REDIRECT_URI=https://ontology.lvh.me/v1/auth/sso/callback`，未写入 client ID 或密钥。
- 再次严格 TLS 核对认证源 Discovery，返回 issuer 与上述配置一致。现有运行配置仍缺 client ID、client secret，因此 SSO 保持未启用，密码登录能力保留。
- 本轮检查未发现 8002 应用监听；接口及路径的测试证明不等于浏览器可访问或完成实际部署。

## 自动验证

| 层次 | 实际结果 |
| --- | --- |
| 采购服务完整 pytest 套件 | **102 passed，47 skipped**，无失败 |
| 前端完整 Vitest 套件 | **18 passed，7 个测试文件** |
| TypeScript 与 Vite 生产构建 | **通过** |
| `git diff --check` | **通过** |
| 真实认证源 Discovery | **HTTPS 200，严格 TLS 校验通过**；issuer 为 `https://sso.lvh.me:8443`，支持 RS256 |
| 密码入口直接刷新 | TestClient 使用临时前端目录验证 `/login/password` 返回页面；不存在的 `/v1/*` 不被 SPA 页面吞掉 |

47 个跳过项依赖未配置的外部 Fuseki 测试环境，不能记作通过。套件另有既存的 Pandas Copy-on-Write 和 LinkML 弃用警告，不是本功能引入的测试失败。

后端测试复用现有 Python 环境，`PYTHONPATH` 明确指向本隔离工作区，执行完整服务 `pytest -q`；前端在本工作区执行 `npm test -- --run`、`npm run build`。不运行真实付费模型调用或发送短信。

## 关键证据

- `test_sso_identity.py` 使用真实 SQLite 并发操作，验证 `(issuer, sub)` 唯一、相同登录名不合并、待分配令牌不能当业务/MCP 令牌、分配幂等与冲突、单次审计、越权和过期拒绝。
- `test_sso.py` 使用真实 RSA 签名和 httpx MockTransport 替代远程认证中心，校验授权请求、Basic 编码、PKCE 换码参数、错误签名/issuer/audience/nonce/auth_time、UserInfo sub 不一致、错误浏览器、重放、过期事务、网络失败及异常 Discovery。
- `test_sso_api.py` 使用真实 SQLite 和真实 API 鉴权，仅替代不在本测试范围内的 RDF 存储。验证待分配身份的业务访问拒绝、管理员分配/激活/退出、原密码登录、Origin/CSRF、重复回调参数、固定密码路径。
- `LoginPages.test.tsx` 验证默认 SSO、未配置提示、所有本地账号的密码入口、待分配状态/刷新/退出、平台分配和失败重试。

## 独立审查与修复

独立审阅者检查完整实现，未发现待分配提权、跨企业授权或分配竞态，发现并复现两项问题：

1. `client_secret_basic` 原样编码导致包含 `+`、`%`、冒号或空格的密钥不能正确换码。新增测试先失败，再使用 OAuth 要求的逐字段 form 编码修复；模拟服务器独立解码 Basic 验证原始凭据，不用同一编码函数计算测试期望。
2. Discovery 中整数类型端点导致异常逃逸为 500。新增用例先失败，再在 URL 信任边界检查字符串类型，按既有安全错误处理返回拒绝。

两项修复后的最终完整服务测试为 102 passed、47 skipped。前端再次全测和构建通过。参考：[RFC 6749 §2.3.1](https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1)。

## 实施决定与保留边界

- 用户明确要求直接设计、计划、实现，不再确认；因此连续执行，不重复等待设计或计划批准。
- 使用 PowerShell 记录执行过程，替代技能中 bash 专用辅助脚本，不改变产品行为。
- 不自动合并账号；一个 SSO 身份只首次分配到一个企业，不做转企业。若需关联老账号或转企业，应另行设计显式操作，不能靠改 claim 或同名自动识别。
- 退出仅清理本工作台当前会话；保留一小时本地会话上限，中心退出/停用不即时撤销已签发工作台会话。本地账号和企业状态仍逐次鉴权。
- 部分 SSO 配置继续禁用 SSO 并保留密码登录，防止平台管理员被锁出。
- 同一浏览器重新开始 SSO 会覆盖先前绑定 Cookie，旧登录回调失败关闭；不新增多标签并行登录机制。
- 代理日志屏蔽、实际部署 CA 信任、真实跨站 Cookie 属于部署和浏览器联调门，本轮不能判定通过。

## 待真实联调

1. 用户通过私有配置提供 client ID 和 client secret，认证中心精确登记 `https://ontology.lvh.me/v1/auth/sso/callback`；若环境域名不同，成对更新登记和后端 `PROCUREMENT_SSO_REDIRECT_URI`。
2. 确认工作台 HTTPS 部署、运行容器 CA 信任及代理回调日志屏蔽已生效，再重启本服务加载私有配置。
3. 实际浏览器完成 SSO 新用户登录、等待分配、超级管理员密码登录分配、用户激活/重登、退出和跨企业拒绝；分别留证，不用模拟 HTTP 结果替代。

未验证真实 SSO 登录、短信、浏览器 SameSite 行为、真实运行库升级或 WSL/UAT/生产部署。本记录不是正式业务验收。
