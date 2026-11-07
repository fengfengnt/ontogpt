# Fuseki 镜像更名与旧资源清理

日期：2026-11-04。状态：**完成，当前知识数据保持**。

用户明确选择“保留当前知识数据，仅删除旧镜像及确认不再使用的旧资源”。本次使用现有已验证 6.2.0 内容重新命名，不升级 Jena 引擎，不更改应用版本。

| 项目 | 当前实际值 |
| --- | --- |
| Fuseki 镜像 | `yunhezhiyuan-ontology-fuseki:6.2.0` |
| 镜像 ID | `sha256:79915711b7359174eb045c93cca61bafff352ea29af76e514f2b55f4a68f2334`，与更名前相同 |
| Fuseki 容器 / 服务键 | `ontology-fuseki` |
| Compose 分组 | `yunhezhiyuan`，已核对实际容器标签 |
| 数据卷 | `procurement-ontology_fuseki_data`，仍为原卷 |
| 本机映射 | `127.0.0.1:3032` → 容器3030，未改为公开数据库入口 |
| 应用 | `yunhezhiyuan-ontology-0.1.1`，容器 ID 不变，恢复 healthy |
| 前端 / 后端文档 | https://ontology.lvh.me/ / https://ontology.lvh.me/docs |

## 切换与保留

新镜像标签指向原镜像 ID，核对后导出至 `D:/Code/deploy/local-deploy/releases/yunhezhiyuan-ontology-fuseki/local/6.2.0/`；镜像包与 SHA256 已验证。不重编译或覆盖原镜像内容。

先停止本体应用，在原 Fuseki 仍运行时执行现有双库备份，核验 SQLite 完整性及所有备份文件摘要。备份保留于目标受限路径 `/home/fengfeng/yunhezhiyuan/ontology/runtime/backups/pre-fuseki-image-rename-20261104/`；配置与执行证据在 `ontology/evidence/fuseki-image-rename-20261104/`。

随后停止原 Fuseki，更新本项目生效 Compose 中的镜像引用，仅重建 `ontology-fuseki`。确认新容器使用同一镜像 ID、同一数据卷与原 Shiro 凭据，数据库就绪后启动原应用。没有让两个进程同时写 TDB2，没有删除数据卷、重新注册数据集或初始化账号。

## 实际验证

- SQLite 所有原表逐行与切换前备份相同：账号4、企业3、会话29、服务令牌10、启用schema2、激活审计2，SSO新表仍为空。
- 4 个 RDF 域与备份逐图同构，树/本体发布版本保持：platform127、test_buyer1 418、test_buyer2 32、test_supplier1 228四元组。
- 应用容器 ID 保持、状态 healthy；其余26个保留容器没有重建。
- 前端、密码入口、健康、后端文档、SSO配置端点均经严格TLS返回200。
- 当前镜像名、实际 Compose 分组、原数据卷及旧资源删除均再次核对。

## 已清理与未删除的数据

- 已删除停用旧容器 `ontology-fuseki-before-migration`，确认其未运行且属于原 `procurement-ontology` 项目。删除容器时未使用删卷参数。
- 已移除旧镜像标签 `procurement-fuseki:6.2.0`。清理前确认已无容器使用此引用，新标签及运行容器继续引用相同镜像内容。
- 仅发现一个相关数据卷，即当前在用的 `procurement-ontology_fuseki_data`；它也曾被停用旧容器挂载，不能当作废弃数据删除。没有可独立清理的旧数据卷，没有删除任何卷、现有知识、运行秘密、备份或草案。
- 现行源码及WSL Compose已更新。历史发布包保留原校验和，不改写其旧镜像引用；重用历史配置时应采用当前新镜像名及同一数据卷。

本次没有改应用镜像、用户密码、证书或共享 Nginx/中心服务，没有执行付费模型或真实SSO登录，也没有创建Git提交或推送。
