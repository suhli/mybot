# Shell 与 Python

本仓库依赖安装在仓库根目录的 **uv 虚拟环境**（`.venv`）。Agent 通过 **Bash** 跑 `python` 时，必须使用与主进程相同的解释器，否则会落到系统 Python，出现 `ModuleNotFoundError`（例如缺 `httpx`）。

- **在 Linux 容器内**：使用 `.venv/bin/python` 或 `uv run python`；不要单独写裸命令 `python`（除非已确认 `PATH` 以 `.venv/bin` 开头）。
- **在本地开发机**：优先 `uv run python ...`，或显式 `.venv/Scripts/python.exe`（Windows） / `.venv/bin/python`（Unix）。

涉及 `lib.tasks`、`lib.newsnow_client` 等模块的一行式调用，请写成例如：

```bash
.venv/bin/python -c "from lib.tasks.get_hot_news import run_get_hot_news; print(run_get_hot_news())"
```

容器镜像已在 `Dockerfile` 中把 `/app/.venv/bin` 加入 `PATH`，与本文档一致即可。
