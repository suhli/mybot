from __future__ import annotations

import json
from pathlib import Path

AGENT_SESSIONS_FILE = Path(".weixin_py") / "claude_sessions.json"


def load_agent_sessions() -> dict[str, str]:
    if not AGENT_SESSIONS_FILE.exists():
        return {}
    raw = json.loads(AGENT_SESSIONS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, str) and value:
            out[key] = value
    return out


def save_agent_sessions(sessions: dict[str, str]) -> None:
    AGENT_SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AGENT_SESSIONS_FILE.write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
