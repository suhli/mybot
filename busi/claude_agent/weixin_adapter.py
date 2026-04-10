from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

from lib.claude.agent import ClaudeAgentRunConfig, format_reply_chunks, run_agent_reply_sync
from lib.claude.sessions import load_agent_sessions, save_agent_sessions
from lib.weixin_bot.daemon import PersonalWeixinDaemon

logger = logging.getLogger(__name__)


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
        logger.debug("WEIXIN_CLAUDE_ENABLED 未开启，跳过注册 Claude handler")
        return

    lock = threading.Lock()
    sessions: dict[str, str] = load_agent_sessions()
    logger.info("已注册微信 Claude handler（DEBUG 可查看 SDK 流式中间输出）")

    def handler(event: dict[str, Any]) -> None:
        from_user = str(event.get("from_user_id", "") or "")
        text = str(event.get("text", "") or "").strip()
        context_token = str(event.get("context_token", "") or "")

        if not from_user or not text:
            return

        cfg = weixin_claude_run_config()
        logger.debug("Claude handler 入站 from=%s text_len=%s", from_user, len(text))

        with lock:
            # Local fallback: some non-official backends may not support built-in /clear.
            if text == "/clear":
                if from_user in sessions:
                    sessions.pop(from_user, None)
                    save_agent_sessions(sessions)
                    logger.info("已清空会话上下文 from=%s", from_user)
                    daemon.send_text(from_user, "已清空当前会话上下文。", context_token=context_token)
                else:
                    daemon.send_text(from_user, "当前没有可清空的会话上下文。", context_token=context_token)
                return

            resume_id = sessions.get(from_user)
            logger.debug("Claude resume_session_id=%s", resume_id or "(none)")
            try:
                reply, new_session_id = run_agent_reply_sync(
                    text,
                    channel_user_id=from_user,
                    resume_session_id=resume_id,
                    config=cfg,
                    session_slot_prefix="wx",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Claude Agent 调用失败: %s", exc)
                daemon.send_text(
                    from_user,
                    f"[Claude] 调用失败: {exc}",
                    context_token=context_token,
                )
                return

            if new_session_id:
                sessions[from_user] = new_session_id
                save_agent_sessions(sessions)

        logger.debug(
            "Claude 回合结束 reply_len=%s new_session_id=%s",
            len(reply),
            new_session_id,
        )
        chunks = format_reply_chunks(reply, config=cfg)
        logger.debug("Claude 回复拆分为 %s 条微信分片", len(chunks))
        for i, chunk in enumerate(chunks):
            logger.debug(
                "Claude 发送分片 %s/%s len=%s preview=%s",
                i + 1,
                len(chunks),
                len(chunk),
                chunk[:120].replace("\n", " ") + ("…" if len(chunk) > 120 else ""),
            )
            daemon.send_text(from_user, chunk, context_token=context_token)

    daemon.add_message_handler(handler)
