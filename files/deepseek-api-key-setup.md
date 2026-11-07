# DeepSeek 配置记录

## 持久保存 API key

在 OntoGPT 项目目录的 PowerShell 中运行：

```powershell
uv run runoak set-apikey -e deepseek-key "<替换为你的 DeepSeek API key>"
```

`-e` 后面是凭据名称 `deepseek-key`，最后一个参数才是 API key。此命令将凭据交给 Oaklib 保存；不要把真实 key 提交到 Git 或写入项目文件。

## Web 测试

- 模型：`deepseek/deepseek-flash`
- API Base：通常可省略，LiteLLM 会按模型服务商解析默认地址；DeepSeek 官方地址为 `https://api.deepseek.com`。
- 启动服务：`uv run start`
- 打开：`http://127.0.0.1:8000/`

若需排查 endpoint，可在启动服务的进程中设置 `DEEPSEEK_API_BASE=https://api.deepseek.com`。key 保存后，应使用同一 Windows 用户运行服务。
