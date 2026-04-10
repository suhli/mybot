from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

logger = logging.getLogger(__name__)


def repository_root() -> Path:
    """本仓库根目录（含 pyproject.toml），用于 Claude Code / Agent SDK 的 project cwd。"""
    return Path(__file__).resolve().parents[2]


@dataclass
class ClaudeAgentRunConfig:
    """单次 Agent 调用的运行参数（可由业务层注入或从环境变量构造）。"""

    permission_mode: str = "plan"
    model: str | None = None
    cwd: Path | None = None
    cli_path: Path | None = None
    chunk_size: int = 1800

    @classmethod
    def from_env(cls, prefix: str = "CLAUDE_AGENT") -> ClaudeAgentRunConfig:
        perm = os.environ.get(f"{prefix}_PERMISSION_MODE", "plan").strip() or "plan"
        model = os.environ.get(f"{prefix}_MODEL", "").strip() or None
        cwd_raw = os.environ.get(f"{prefix}_CWD", "").strip()
        cli_raw = os.environ.get(f"{prefix}_CLI_PATH", "").strip()
        chunk_raw = os.environ.get(f"{prefix}_CHUNK", "1800").strip()
        try:
            chunk_size = int(chunk_raw) if chunk_raw else 1800
        except ValueError:
            chunk_size = 1800
        return cls(
            permission_mode=perm,
            model=model,
            cwd=Path(cwd_raw) if cwd_raw else repository_root(),
            cli_path=Path(cli_raw) if cli_raw else None,
            chunk_size=max(256, chunk_size),
        )


def _effective_cwd(config: ClaudeAgentRunConfig) -> Path:
    return config.cwd if config.cwd is not None else repository_root()


def session_slot_for_user(channel_user_id: str, *, slot_prefix: str = "wx") -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", channel_user_id).strip("_")[:64]
    base = safe if safe else "default"
    return f"{slot_prefix}_{base}"


def _chunk_text(text: str, max_len: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_len])
        start += max_len
    return chunks


def format_reply_chunks(reply: str, config: ClaudeAgentRunConfig | None = None) -> list[str]:
    cfg = config or ClaudeAgentRunConfig.from_env()
    return _chunk_text(reply, max_len=cfg.chunk_size)


async def _chat_turn_async(
    user_text: str,
    *,
    resume_session_id: str | None,
    sdk_session_slot: str,
    config: ClaudeAgentRunConfig,
) -> tuple[str, str | None]:
    permission_mode = cast(
        Literal["default", "acceptEdits", "plan", "bypassPermissions", "dontAsk", "auto"],
        config.permission_mode,
    )
    options = ClaudeAgentOptions(
        permission_mode=permission_mode,
        resume=resume_session_id,
        model=config.model,
        cwd=_effective_cwd(config),
        cli_path=config.cli_path,
    )

    reply_parts: list[str] = []
    out_session_id: str | None = None

    async with ClaudeSDKClient(options) as client:
        logger.debug("Claude SDK query: %s", user_text)
        await client.query(user_text, session_id=sdk_session_slot)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                logger.debug(
                    "Claude SDK AssistantMessage blocks=%s",
                    len(msg.content),
                )
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        logger.debug("Claude assistant TextBlock: %s", block.text)
                        reply_parts.append(block.text)
                    else:
                        logger.debug(
                            "Claude assistant non-text block: %s %r",
                            type(block).__name__,
                            block,
                        )
            elif isinstance(msg, ResultMessage):
                logger.debug(
                    "Claude SDK ResultMessage is_error=%s session_id=%s result=%r errors=%r",
                    msg.is_error,
                    msg.session_id,
                    msg.result,
                    msg.errors,
                )
                out_session_id = msg.session_id or out_session_id
                if msg.is_error:
                    err_bits: list[str] = []
                    if msg.result:
                        err_bits.append(str(msg.result))
                    if msg.errors:
                        err_bits.extend(str(e) for e in msg.errors)
                    if err_bits:
                        reply_parts.append("[Claude 错误] " + " | ".join(err_bits))
                break
            else:
                logger.debug(
                    "Claude SDK message %s: %r",
                    type(msg).__name__,
                    msg,
                )

    reply = "\n".join(p for p in reply_parts if p).strip()
    if not reply:
        reply = "（Claude 未返回可读文本）"
    return reply, out_session_id


def run_agent_reply_sync(
    user_text: str,
    *,
    channel_user_id: str,
    resume_session_id: str | None,
    config: ClaudeAgentRunConfig | None = None,
    session_slot_prefix: str = "wx",
) -> tuple[str, str | None]:
    cfg = config or ClaudeAgentRunConfig.from_env()
    slot = session_slot_for_user(channel_user_id, slot_prefix=session_slot_prefix)
    return asyncio.run(
        _chat_turn_async(
            user_text,
            resume_session_id=resume_session_id,
            sdk_session_slot=slot,
            config=cfg,
        )
    )
