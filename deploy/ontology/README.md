# Ontology 本地镜像与 HTTPS 发布

项目根目录 `VERSION` 是发布版本唯一来源，当前用户选择 `0.1.1`；Python/npm 包元数据版本不作为镜像发布版本。应用镜像 `yunhezhiyuan-ontology-<VERSION>:local`、容器 `yunhezhiyuan-ontology-<VERSION>`，Compose 项目 `yunhezhiyuan`。前端、API、MCP 由同一应用镜像提供。

Fuseki 当前镜像为 `yunhezhiyuan-ontology-fuseki:6.2.0`，服务键/容器 `ontology-fuseki`、原数据卷和凭据保持；详见 [更名与旧资源清理](../../docs/procurement-ontology/fuseki-image-rename-2026-11-04.md)。

## 构建与归档

```powershell
python deploy/ontology/prepare-build.py <新的构建上下文目录>
```

脚本读取实际工作文件：只导出 Git 已跟踪且在应用白名单中的路径，另显式加入新建的 VERSION、Dockerfile、entrypoint.py。可以发布未提交的本次变更，不要求提交或清理原有工作；未跟踪的秘密、runtime、node_modules、宿主 Git 历史不进入上下文。`seed/.build-source.json` 保存实际文件摘要、来源 HEAD 与版本；`release.txt` 是由这些输入生成的内容指纹，不冒充 Git 提交。

在 WSL 构建上下文中执行：

```bash
version="$(cat VERSION)"
docker build --network host --build-arg ONTOLOGY_VERSION="$version" --build-arg ONTOLOGY_REVISION="$(cat revision.txt)" --build-arg ONTOLOGY_RELEASE="$(cat release.txt)" -t "yunhezhiyuan-ontology-$version:local" .
```

镜像内 VERSION、OCI version/revision 标签与内容指纹均需核对。构建后导出 Docker 镜像包，归档至 `D:/Code/deploy/local-deploy/releases/yunhezhiyuan-ontology/local/<VERSION>/`，附 SHA256、公开 Compose/脚本和非敏感发布记录。不要归档 `.env`、身份数据库、私钥、运行凭据或数据库备份。

## 部署与保留

实际运行目录 `/home/fengfeng/yunhezhiyuan/ontology/`，共用 HTTPS/Nginx 资料以 `D:/Code/deploy/local-deploy` 为准。仅切换 `ontology-app` 服务键，不重建现有 Fuseki、中心后端或共享 Nginx。

- 保留 `runtime/control.sqlite3`、原私有 `runtime/.env`、`workspace/releases/`、`workspace/drafts/` 及 `secrets/credentials.json`。
- Fuseki 保留服务名 `ontology-fuseki`、原镜像和 external volume `procurement-ontology_fuseki_data`；新应用沿用原企业、数据集前缀、启用 schema 和模型设置。
- 新镜像按内容指纹初始化独立的发布 Git 目录，原发布和草案保留。不能让两个应用同时写同一运行库。
- 应用私有配置使用 `PROCUREMENT_SSO_ISSUER=https://sso.lvh.me` 与精确 callback；缺少 client ID/secret 时 SSO 保持禁用，本地密码登录可用。
- 应用容器增加 `sso.lvh.me:host-gateway`；使用实际 172.17.0.1 可信 HTTPS 入口。CA bundle 由标准公共根和现有公开 local-ca.pem 合并，只读挂载 `/secrets/ca-bundle.pem`，保留其他 HTTPS 调用能力，不关闭证书校验。

将本目录 Compose、compose.sh 和项目 VERSION 发布到上述运行目录；deployment.env 参考示例并沿用实际部署路径与精确信任代理 IP。所有后续操作通过包装脚本读取同目录 VERSION：

```bash
bash /home/fengfeng/yunhezhiyuan/ontology/compose.sh config --quiet
bash /home/fengfeng/yunhezhiyuan/ontology/compose.sh up -d --no-build --no-deps ontology-app
```

切换前先停止旧应用，用旧发布入口完成 SQLite/Fuseki/schema 双库备份并核验清单与摘要；备份保存在目标受限路径。新应用复用同一数据和凭据，不 bootstrap 新账号。旧镜像和原 Compose/deployment.env 留作回退；回退只能在停止新应用后，使用同一最新数据与原凭据恢复旧应用，不能覆盖为过期 SQLite 副本。禁止 `down -v`、`--remove-orphans` 和全局清理。

## 交付地址与验证

- 前端：`https://ontology.lvh.me/`
- 通用用户名密码登录：`https://ontology.lvh.me/login/password`
- 后端 API：`https://ontology.lvh.me/v1/`，健康检查 `/health`，接口文档 `/docs`
- MCP：`https://ontology.lvh.me/mcp/`

HTTPS 在共用 Nginx 终止，上游 8002 仅绑定宿主 loopback。`PROCUREMENT_PUBLIC_ORIGIN` 与可信代理按原部署执行，MCP/Host/Origin/CSRF 继续校验。最终验证页面及资源、API、数据/账号/草案保留、镜像身份和容器 DNS/CA；没有 client 凭据不宣称真实 SSO 登录通过。本次不部署 UAT，不自动触发短信或付费模型。
