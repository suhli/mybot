from __future__ import annotations

import base64
import random
from typing import Any

import httpx

from .models import DEFAULT_BASE_URL


class WeixinClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 35.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self.client.close()

    def _uin_header(self) -> str:
        value = str(random.getrandbits(32))
        return base64.b64encode(value.encode("utf-8")).decode("utf-8")

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "AuthorizationType": "ilink_bot_token",
            "X-WECHAT-UIN": self._uin_header(),
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get(self, endpoint: str) -> dict[str, Any]:
        resp = self.client.get(f"{self.base_url}/{endpoint}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
        resp = self.client.post(
            f"{self.base_url}/{endpoint}",
            json=payload,
            headers=self._headers(token),
        )
        resp.raise_for_status()
        return resp.json()

    def get_bot_qrcode(self, bot_type: str) -> dict[str, Any]:
        return self._get(f"ilink/bot/get_bot_qrcode?bot_type={bot_type}")

    def get_qrcode_status(self, qrcode: str) -> dict[str, Any]:
        return self._get(f"ilink/bot/get_qrcode_status?qrcode={qrcode}")

    def get_updates(self, token: str, get_updates_buf: str = "") -> dict[str, Any]:
        return self._post(
            "ilink/bot/getupdates",
            {"get_updates_buf": get_updates_buf},
            token=token,
        )

    def send_text(self, token: str, to_user_id: str, text: str, context_token: str = "") -> dict[str, Any]:
        return self._post(
            "ilink/bot/sendmessage",
            {
                "msg": {
                    "to_user_id": to_user_id,
                    "context_token": context_token,
                    "item_list": [{"type": 1, "text_item": {"text": text}}],
                }
            },
            token=token,
        )

