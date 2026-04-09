from __future__ import annotations

from dataclasses import dataclass


DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
DEFAULT_BOT_TYPE = "3"


@dataclass(slots=True)
class Session:
    bot_token: str
    bot_id: str
    user_id: str | None = None
    base_url: str = DEFAULT_BASE_URL
    get_updates_buf: str = ""

