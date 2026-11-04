# Ontology 镜像与共用 HTTPS

设计见 `docs/superpowers/specs/2026-11-04-ontology-wsl-https-design.md`。共用域名、证书和 Nginx 运维以 SSO 工程 `docs/deployment/local-wsl-yunhezhiyuan.md` 为准。

## 构建

先提交审核后的变更。构建脚本只从 Git HEAD 导出明确允许的源文件，不读取未提交文件或私有运行目录：

```powershell
python deploy/ontology/prepare-build.py <新的构建上下文目录>
```

将该目录复制到 Linux 后，从 `release.txt` 读取完整提交 ID：

```bash
docker build --network host --build-arg ONTOLOGY_RELEASE="$(cat release.txt)" -t ontology-app:<release> .
```

Node 和 Python 基础镜像固定摘要；Python 依赖使用服务自己的 uv.lock。镜像不含凭据或宿主 Git 历史。使用相同 release ID 重新构建出不同文件时，入口拒绝复用已有发布目录；应发布新提交。

## 本地部署

`/home/fengfeng/yunhezhiyuan/ontology/` 下准备 `compose.yaml`（本目录副本）、`deployment.env`（参考示例）、`runtime/`、`workspace/`、`secrets/`。可写目录归 UID/GID 1000，凭据文件限制读取权限。

- `runtime/control.sqlite3`：由旧运行目录备份迁移，不能重新初始化已有账号。
- `runtime/.env`：原模型设置与显式 `PROCUREMENT_API_KEY`（若原来依赖提供方凭据，安全读取后注入此私有文件），以及既有数据集前缀；不复制 Windows 绝对路径。
- `secrets/credentials.json`、`secrets/shiro.ini`：既有 Fuseki 身份，只读挂载，不重新生成口令。
- `workspace/releases/<commit>`：从镜像种子初始化的本地 Git 仓库；`workspace/drafts/` 保存新 schema 草案。重建不丢失，升级按提交隔离；旧发布目录保留供审阅。

Fuseki 复用 external volume `procurement-ontology_fuseki_data`。迁移前备份并停止旧写入者，禁止新旧 Fuseki 同时使用该卷。

```bash
cd /home/fengfeng/yunhezhiyuan
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml config --quiet
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml up -d --no-build --no-deps ontology-fuseki ontology-app
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml ps ontology-app ontology-fuseki
```

管理命令必须使用相同发布入口、`runtime`、网络和环境。备份前只停止应用，Fuseki 保持运行；一次性容器明确命名：

```bash
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml stop ontology-app
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml run --rm --no-deps --name ontology-backup ontology-app backup --destination /runtime/backups/<新备份名>
docker compose --env-file ontology/deployment.env -f compose.yaml -f ontology/compose.yaml up -d --no-deps ontology-app
```

停止使用 `stop ontology-app ontology-fuseki`，不使用 `down`、`--remove-orphans` 或删卷。共享组内的 backend/nginx 由其他工程管理。

## HTTPS 与调用

本地入口 `https://ontology.lvh.me/`；API 在 `/v1/`，MCP 在 `/mcp/`，各自保留原身份校验。Nginx 转发本机 8002 并覆盖 HTTPS 头。`ONTOLOGY_PROXY_IP` 必须为实测代理 peer，禁止 `*` 或整段网络信任。Windows/原生 WSL 使用既有 CA；Docker 客户端需配置本地域名指向宿主网关，且只分发公开 CA，不复制私钥。一次性探测容器也使用 `ontology-` 前缀。

严格验证：

```bash
curl --noproxy ontology.lvh.me --cacert /home/fengfeng/yunhezhiyuan/certs/local-ca.pem https://ontology.lvh.me/health
```

UAT 部署采用同一镜像，显式配置 `ONTOLOGY_PUBLIC_ORIGIN`、可信代理、实际证书与新数据路径。当前只有单实例写入；迁移后的唯一活动目录在 WSL，旧 Windows 目录为回退副本。旧 Windows schema 草案单独归档保留，不直接复制其绝对路径 Git 引用到 Linux。
