# FH5 Painter GPU V1.1.1-Beta

---

## 本次更新 / What's Changed

### 新功能 / New Features

- **多语言界面**：支持简体中文、繁體中文、English，切换即时生效
  / **Multi-language UI**: 简体中文 / 繁體中文 / English, switch instantly
- **暂停 / 继续**：生成过程中可随时暂停与继续渲染器
  / **Pause / Resume**: pause and resume the renderer at any time
- **自动下载依赖**：首次启动自动从 GitHub Releases 检查并下载
  `forza-painter-geometrize-go.exe` 与 `forza-painter.exe`
  / **Auto-download tools**: fetch renderer and painter from GitHub on first launch
- **参数记忆**：优先读取 `runtime/custom.ini` 里的 `stopAt` / `saveAt` / `saveEvery`
  / **Parameter memory**: load params from `runtime/custom.ini` if present
- **配置文件抽离**：新增 `app_config.py`，版本号、下载源、多语言字典集中管理
  / **Config extraction**: new `app_config.py` for version, sources and i18n

### 修复 / Fixes

- **修复 backend 参数拼写**：`--backend` → `-backend`（单破折号）
  Vulkan 后端现可正常使用
  / **Fixed backend flag**: single-dash `-backend` so Vulkan works
- **修复关闭 GUI 后渲染器仍在后台**：关窗口时自动终止进程树
  / **Fixed orphan renderer**: kill the whole process tree on exit
- **修复生成时卡死无提示**：渲染器启动即退出时给出明确错误
  / **Fixed silent hang**: clear error if renderer exits immediately
- **修复文件更新 / 报错 / 格式相关的若干 BUG**
  / **Various bug fixes**: file update, error handling, format

### 重构 / Refactor

- 拆分为 `main.py` / `tools.py` / `gpu_geometrize.py` / `app_config.py`
  / Split into four modules for clarity

---


## 已知问题 / Known Issues

- **Vulkan 后端**：部分显卡驱动过旧时可能启动失败，日志区会提示。
  可切换到 OpenCL 后端，或更新显卡驱动
  / **Vulkan backend**: may fail with outdated GPU drivers, switch to OpenCL
- **反作弊游戏**：本项目仅生成 JSON，与游戏内反作弊无关
  / **Anti-cheat**: this tool only generates JSON, unrelated to in-game anti-cheat

---

**完整更新日志 / Full Changelog**: 见仓库 commit 历史。