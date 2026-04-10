from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from lib.claude.agent import ClaudeAgentRunConfig, format_reply_chunks, run_agent_reply_sync
from lib.claude.sessions import load_agent_sessions, save_agent_sessions
from lib.weixin_bot.daemon import PersonalWeixinDaemon


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def weixin_claude_run_config() -> ClaudeAgentRunConfig:
    """先读通用 CLAUDE_AGENT_*，再用 WEIXIN_CLAUDE_* 覆盖（兼容旧环境变量）。"""
    cfg = ClaudeAgentRunConfig.from_env("CLAUDE_AGENT")

    perm = os.environ.get("WEIXIN_CLAUDE_PERMISSION_MODE", "").strip()
    if perm:
        cfg.permission_mode = perm

    model = os.environ.get("WEIXIN_CLAUDE_MODEL", "").strip()
    if model:
        cfg.model = model

    cwd = os.environ.get("WEIXIN_CLAUDE_CWD", "").strip()
    if cwd:
        cfg.cwd = Path(cwd)

    cli = os.environ.get("WEIXIN_CLAUDE_CLI_PATH", "").strip()
    if cli:
        cfg.cli_path = Path(cli)

    chunk = os.environ.get("WEIXIN_CLAUDE_CHUNK", "").strip()
    if chunk:
        try:
            cfg.chunk_size = max(256, int(chunk))
        except ValueError:
            pass

    return cfg


def register_weixin_claude_handler(daemon: PersonalWeixinDaemon) -> None:
    """
    向微信常驻进程注册 Claude Agent 文本回复 handler。
    需设置环境变量 WEIXIN_CLAUDE_ENABLED=1 才会生效。
    """
    if not _env_truthy("WEIXIN_CLAUDE_ENABLED"):
        return

    lock = threading.Lock()
    sessions: dict[str, str] = load_agent_sessions()

    def handler(event: dict[str, Any]) -> None:
        from_user = str(event.get("from_user_id", "") or "")
        text = str(event.get("text", "") or "").strip()
        context_token = str(event.get("context_token", "") or "")

        if not from_user or not text:
            return
        if daemon.session.user_id and from_user == str(daemon.session.user_id):
            return

        cfg = weixin_claude_run_config()

        with lock:
            resume_id = sessions.get(from_user)
            try:
                reply, new_session_id = run_agent_reply_sync(
                    text,
                    channel_user_id=from_user,
                    resume_session_id=resume_id,
                    config=cfg,
                    session_slot_prefix="wx",
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] Claude Agent 调用失败: {exc}")
                daemon.send_text(
                    from_user,
                    f"[Claude] 调用失败: {exc}",
                    context_token=context_token,
                )
                return

            if new_session_id:
                sessions[from_user] = new_session_id
                save_agent_sessions(sessions)

        for chunk in format_reply_chunks(reply, config=cfg):
            daemon.send_text(from_user, chunk, context_token=context_token)

    daemon.add_message_handler(handler)
