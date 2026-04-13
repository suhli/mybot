FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and sync dependencies
RUN uv venv && uv sync --frozen

# Bash 等子进程里的 `python` 须指向项目 venv（否则缺 httpx 等依赖）
ENV PATH="/app/.venv/bin:${PATH}" \
    VIRTUAL_ENV="/app/.venv"

# Copy project files
COPY . .

# Claude Code CLI 禁止在 root 下使用 bypassPermissions（--dangerously-skip-permissions）
RUN useradd --create-home --uid 1000 --user-group mybot \
    && chown -R mybot:mybot /app

USER mybot

# 先激活 venv 再跑（与直接 .venv/bin/python 等价；exec 使 PID 1 为 python）
CMD ["/bin/sh", "-c", ". .venv/bin/activate && exec python main.py"]
