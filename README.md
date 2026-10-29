# updateAppsFromGithub

按系统与 CPU 架构筛选 GitHub Release 资产，并自动下载指定的便携软件。ZIP 文件下载后会解压，其他格式（如 7z）保留原文件。

## 运行

需要 Python 3.10+，无需第三方运行依赖。

```bash
python updateAppsFromGithub.py
```

在 Windows 下默认保存到 `%LOCALAPPDATA%/updateAppsFromGithub/`，在 macOS/Linux 下默认保存到 `~/Applications/updateAppsFromGithub/`（具体名称由脚本启动路径的文件名决定）。

在脚本顶部修改 `CONFIGS` 可以增删 GitHub 仓库和资产名称关键词（`;` 分隔）。可选的 `GITHUB_TOKEN` 建议仅在本地设置，不要提交真实令牌。

## 测试

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

> 注意：当前按提供的原始逻辑禁用了 SSL 证书验证，存在中间人攻击风险。分片下载也未校验 `206 Partial Content`、分片长度或文件校验和；请勿将其用于高信任度的软件分发场景。建议后续加固。
