# 本地 Fuseki/TDB2 部署

本配置用于采购本体 MVP 的 Ubuntu WSL Docker 环境。固定 Apache Jena Fuseki `6.2.0`，从官方二进制构建，校验 SHA-512；`Dockerfile` 固定 Java 基础镜像。端口 `127.0.0.1:3032`，Compose 项目 `procurement-ontology`，业务数据位于独立卷 `procurement-ontology_fuseki_data`。

## 初始化和启动

先在 `deploy/fuseki/` 创建本地凭据和 Shiro 配置。以下 Python 片段在已有文件时拒绝覆盖；密码不打印，文件不提交 Git。仅用于本机试点，文件应保持只有部署账户可读。

```python
from pathlib import Path
import json
import secrets

runtime = Path("runtime")
runtime.mkdir(exist_ok=True)
if any((runtime / name).exists() for name in ("credentials.json", "shiro.ini")):
    raise SystemExit("配置已存在，请核对现有文件；不会覆盖")
password = secrets.token_hex(32)
credentials = {"username": "service", "password": password}
with (runtime / "credentials.json").open("x", encoding="utf-8") as stream:
    json.dump(credentials, stream)
with (runtime / "shiro.ini").open("x", encoding="utf-8") as stream:
    stream.write("[users]\nservice = " + password + ",service\n\n[urls]\n"
                 "/$/ping = anon\n/$/** = authcBasic,roles[service]\n"
                 "/** = authcBasic,roles[service]\n")
for path in runtime.iterdir():
    path.chmod(0o600)
```

在 Ubuntu WSL 中切换到本目录，运行 `docker compose up -d --build`。Dockerfile 只安装服务，Shiro 将管理及数据端点都限制为本地服务身份；不使用默认管理员口令。浏览器和 Agent 不持有此凭据，也不直连 Fuseki。

服务和测试使用 `runtime/credentials.json`，路径可通过 `FUSEKI_CREDENTIALS_FILE` 指定。文件内容只由请求客户端读取，不能写入命令行、测试快照或运行日志。配置中的匿名 `/$/ping` 仅用于存活检查。

## 真实事务测试

从 Windows 仓库根目录运行：

```powershell
$env:FUSEKI_TEST_URL = 'http://127.0.0.1:3032'
uv run --project services/procurement_ontology pytest services/procurement_ontology/tests/integration/test_fuseki_atomicity.py -q
```

未指定 `FUSEKI_TEST_URL` 时测试明确跳过。指定后必须实际连接 TDB2，不能用跳过结果表示事务通过。测试仅创建和清理 `test_atomic_` 开头的临时测试数据集，不操作企业数据集。

测试覆盖先写图和指针、再触发缺失文件 `LOAD` 的事务失败；失败后检查旧指针和旧图、新图不存在。另测并发读者只看完整旧版/新版、两个同基础版本发布只有一个生效，以及匿名访问数据端点被拒绝。HTTP 200 本身不表示条件更新已发生。

停止本项目容器可运行 `docker compose stop`；重启用 `docker compose start`。这些命令保留持久卷。不得把清理卷作为普通重启步骤；备份恢复在实施计划 Task 14 单独验证。

## 技术依据

- [Apache Jena 发布与二进制下载](https://jena.apache.org/download/)
- [Fuseki Docker 与持久化](https://jena.apache.org/documentation/fuseki2/fuseki-docker.html)
- [Fuseki Shiro 与管理端点权限](https://jena.apache.org/documentation/fuseki2/fuseki-security.html)

## 已执行证据（2026-10-19）

- Ubuntu WSL Docker Engine `29.7.2`；从 Windows 访问 `http://127.0.0.1:3032`，测试通过。
- Java 基础镜像摘要为 `sha256:227118764cccd3c3294617061aaa93a08309c63a395eefa83e6b35032992ea99`。
- 容器实际镜像 ID 为 `sha256:79915711b7359174eb045c93cca61bafff352ea29af76e514f2b55f4a68f2334`，构建输出确认 Fuseki 官方归档 SHA-512 匹配。
- 容器 `procurement-ontology-fuseki-1`，独立卷 `procurement-ontology_fuseki_data`，仅绑定本机端口 `3032`。
- 上述真实事务测试命令：`4 passed`。包含运行时 LOAD 失败回滚、并发读完整性、同基础版条件发布唯一成功及匿名数据访问拒绝。
- 全服务测试在显式设置 `FUSEKI_TEST_URL` 时为 `32 passed`；此数字只对应当前已实现的领域、身份、schema 加载和事务前提测试。

2026-10-20 已另行完成完整业务发布、实际 Docker 重启和 CLI 双库备份恢复。结果及证据见[本地技术验收记录](../../docs/procurement-ontology/acceptance-2026-10-20.md)，不由本次原子性测试推断。
