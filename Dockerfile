FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Create virtual environment and sync dependencies
RUN uv venv && uv sync --frozen

# Copy project files
COPY . .

# Claude Code CLI 禁止在 root 下使用 bypassPermissions（--dangerously-skip-permissions）
RUN useradd --create-home --uid 1000 --user-group mybot \
    && chown -R mybot:mybot /app

USER mybot

# Run the main entrypoint
CMD [".venv/bin/python", "main.py"]
