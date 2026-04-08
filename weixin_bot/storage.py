from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import Session


SESSION_FILE = Path(".weixin_py") / "session.json"
CONTEXT_TOKENS_FILE = Path(".weixin_py") / "context_tokens.json"


def save_session(session: Session) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(asdict(session), ensure_ascii=False, indent=2), encoding="utf-8")


def load_session() -> Session:
    if not SESSION_FILE.exists():
        raise FileNotFoundError(
            "未找到会话文件 .weixin_py/session.json，请先执行登录命令。"
        )
    raw = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    return Session(**raw)


def save_context_tokens(tokens: dict[str, str]) -> None:
    CONTEXT_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONTEXT_TOKENS_FILE.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_context_tokens() -> dict[str, str]:
    if not CONTEXT_TOKENS_FILE.exists():
        return {}
    raw = json.loads(CONTEXT_TOKENS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    result: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str):
            result[key] = value
    return result

