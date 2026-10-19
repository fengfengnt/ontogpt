# 项目目录结构

状态：MVP 目标结构，待评审；本轮仅创建文档。范围依据见 [MVP 设计](../superpowers/specs/2026-10-19-procurement-ontology-mvp-design.md)。

## 目录总览

```text
ontogpt/
├─ src/ontogpt/
│  ├─ templates/
│  │  ├─ core.yaml / core.py                 # 现有 OntoGPT 核心模板
│  │  └─ company/
│  │     ├─ general_template/README.md       # 编写企业 schema 的参考
│  │     ├─ test_buyer1/computer/v1/
│  │     │  ├─ test_buyer1_computer.yaml
│  │     │  └─ test_buyer1_computer.py        # LinkML 生成
│  │     └─ test_supplier1/computer/v1/
│  │        ├─ test_supplier1_computer.yaml
│  │        └─ test_supplier1_computer.py     # LinkML 生成
│  ├─ io/template_loader.py                 # 现有加载器，作为兼容性检查对象
│  ├─ engines/spires_engine.py              # 复用提取能力
│  └─ webapp/                               # 现有演示应用
├─ services/procurement_ontology/
│  ├─ pyproject.toml                        # 独立服务依赖、入口及测试依赖
│  ├─ schema_registry.yaml                  # 可部署 schema 清单
│  ├─ procurement_ontology/
│  │  ├─ __init__.py
│  │  ├─ models.py                          # 来源、候选、条目、关系、树、版本
│  │  ├─ identity.py                        # 账号、会话、企业范围及权限
│  │  ├─ schema_loader.py                   # 按注册表读取已生成的模板
│  │  ├─ schema_catalog.py                  # SQLite 启用指针和激活审计
│  │  ├─ store.py / rdf_codec.py            # Fuseki 操作与 RDF 映射
│  │  ├─ platform_seed.py                   # 平台初始版本及企业实例化
│  │  ├─ intake.py / extraction.py          # 原文修订与模型提取
│  │  ├─ schema_draft.py                    # 缺口记录与待审 schema 草案
│  │  ├─ governance.py / query.py           # 审核发布与授权读取
│  │  ├─ api.py / mcp_server.py             # FastAPI 与两个只读 MCP tools
│  │  ├─ agent.py / cli.py                  # LangGraph 演示与管理命令
│  │  └─ backup.py                         # 维护窗口备份、恢复
│  └─ tests/
│     ├─ unit/                             # 替身模型、SQLite、接口与权限
│     ├─ integration/                      # 真实 Fuseki、恢复及贯通验证
│     └─ fixtures/supplier-laptop-bid-case.md
├─ frontend/procurement-ontology/
│  ├─ package.json / vite.config.ts
│  ├─ DESIGN.md                            # 实际采用的界面规则
│  └─ src/
│     ├─ App.tsx / api.ts                   # 工作区及同源 API
│     ├─ TreeEditor.tsx / PlatformEditor.tsx
│     ├─ OntologyCanvas.tsx / canvasChanges.ts
│     ├─ AgentPage.tsx
│     ├─ styles/tokens.css                 # 页面和画布共用语义样式
│     └─ *.test.tsx                        # 状态、操作和入口约束测试
├─ deploy/fuseki/
│  ├─ compose.yaml                         # 独立 WSL Docker 部署
│  └─ README.md                            # 版本、端口、卷及验证方法
├─ docs/procurement-ontology/
│  ├─ README.md / directory-structure.md / system-architecture.md
│  ├─ detailed-design.md / frontend-design.md / review-and-validation.md
│  ├─ laptop-knowledge-pack-candidate-v0.md
│  └─ schemas/
│     ├─ README.md
│     ├─ test_buyer1/computer/v1.md
│     └─ test_supplier1/computer/v1.md
├─ docs/superpowers/specs/2026-10-19-procurement-ontology-mvp-design.md
├─ docs/superpowers/plans/2026-10-19-procurement-ontology-mvp.md
└─ tests/fixtures/procurement/laptop-purchase-case.md
```

## 公司、品类、版本三层目录

企业模板以 `company/<company_id>/<category_key>/<schema_version>/` 定位。MVP 的 `category_key` 为 `computer`，显示名称为 `电脑(台式机/笔记本)`。显示名称可以修改，不能据此自动改目录、业务 ID 或启用指针。

两家公司即使某些字段完全相同，也保留各自的 YAML、Python 和 schema 说明文档。新企业或新二级品类沿此结构增加，不把公司差异写进一个充满分支的通用 schema。`general_template` 只是编写参考，和 Fuseki 平台数据集里的“通用本体/通用树”不是同一对象。

升级时增加 `v2/` 和对应 `v2.md`，保留 `v1/`。生成的 Python 不手工维护；修改 YAML 后用固定的生成环境重新生成并计算哈希。注册表登记 YAML、Python、根类与生成器版本，SQLite 单独选择当前启用版本。

## 代码与文档的职责

服务只复用 OntoGPT 的提取与模型调用能力。企业模板采用独立的注册表加载入口，避免现有自定义模板加载器复制文件到根目录或运行时生成 Python。实施时验证相对 LinkML 导入、生成模块导入和构建产物中的嵌套模板，不能只验证开发目录里能够加载。

现有打包配置需要在 Task 5 检查：企业目录下的 YAML/Python 必须进入交付产物，注册表中的相对路径必须在安装后仍可解析。使用的项目内 LinkML 导入依赖也须按版本固定并验证摘要，不能只引用会随仓库变动的未固定文件。新增公司模板不能被现有 Web 演示的模板选择器枚举出来。

业务模块按当前职责拆分；测试与对应服务一起维护。目录图表示文件职责，不要求为了凑目录创建空类、包装器或未使用的模块。

## 运行数据与 Git

SQLite、Fuseki 持久卷、会话、真实企业原文、模型响应和备份属于运行数据，存放位置由部署配置指定。它们不进入 Git。Git 保存 schema、生成产物、可部署注册表、代码、模拟测试资料和评审文档。

Schema 草案写入独立待审工作树的新版本目录，不能切换正在运行服务的代码分支。草案内容应说明新增字段及来源理由；真实企业材料和内部金额不因起草 schema 自动复制进代码仓库。

开发依赖在各自运行平台安装：本地 Python/前端按 Windows 环境使用，Fuseki 在 WSL Docker 中运行；不跨 Windows/WSL 共享 `node_modules`。实际锁文件和镜像版本在实施时固定并记录。
