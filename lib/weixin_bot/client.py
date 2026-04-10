from __future__ import annotations

import base64
import random
import uuid
from typing import Any

import httpx

from .models import DEFAULT_BASE_URL
import logging

logger = logging.getLogger(__name__)

# 与 Node 版 login-qr.ts 一致：服务端长轮询约 35s；读超时需略大，否则易 httpx.ReadTimeout
_LONG_POLL_READ_SEC = 55.0
_SHORT_TIMEOUT = httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0)
_LONG_POLL_TIMEOUT = httpx.Timeout(connect=15.0, read=_LONG_POLL_READ_SEC, write=15.0, pool=15.0)


class WeixinClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float | httpx.Timeout | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        if timeout is None:
            t: httpx.Timeout | float = _SHORT_TIMEOUT
        else:
            t = timeout
        self.timeout = t
        self.client = httpx.Client(timeout=t)

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

    def _get(self, endpoint: str, *, request_timeout: httpx.Timeout | float | None = None) -> dict[str, Any]:
        resp = self.client.get(
            f"{self.base_url}/{endpoint}",
            headers=self._headers(),
            timeout=request_timeout if request_timeout is not None else self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        token: str | None = None,
        *,
        request_timeout: httpx.Timeout | float | None = None,
    ) -> dict[str, Any]:
        resp = self.client.post(
            f"{self.base_url}/{endpoint}",
            json=payload,
            headers=self._headers(token),
            timeout=request_timeout if request_timeout is not None else self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_bot_qrcode(self, bot_type: str) -> dict[str, Any]:
        return self._get(f"ilink/bot/get_bot_qrcode?bot_type={bot_type}")

    def get_qrcode_status(self, qrcode: str) -> dict[str, Any]:
        """长轮询；读超时或网络错误视为仍在等待，与 Node 版 pollQRStatus 一致。"""
        try:
            return self._get(
                f"ilink/bot/get_qrcode_status?qrcode={qrcode}",
                request_timeout=_LONG_POLL_TIMEOUT,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                return {"status": "wait"}
            raise
        except httpx.RequestError:
            return {"status": "wait"}

    def get_updates(self, token: str, get_updates_buf: str = "") -> dict[str, Any]:
        """长轮询；读超时返回空包，便于上层重试，与 Node 版 getUpdates 一致。"""
        try:
            return self._post(
                "ilink/bot/getupdates",
                {"get_updates_buf": get_updates_buf},
                token=token,
                request_timeout=_LONG_POLL_TIMEOUT,
            )
        except httpx.ReadTimeout:
            return {"ret": 0, "msgs": [], "get_updates_buf": get_updates_buf}

    def send_text(self, token: str, to_user_id: str, text: str, context_token: str = "") -> dict[str, Any]:
        logger.info(
            "Sending text to %s (len=%s, has_context_token=%s)",
            to_user_id,
            len(text),
            bool(context_token),
        )
        resp = self._post(
            "ilink/bot/sendmessage",
            {
                "msg": {
                    "from_user_id": "",
                    "to_user_id": to_user_id,
                    "client_id": uuid.uuid4().hex,
                    "message_type": 2,
                    "message_state": 2,
                    "context_token": context_token,
                    "item_list": [{"type": 1, "text_item": {"text": text}}],
                }
            },
            token=token,
        )
        ret = resp.get("ret")
        if isinstance(ret, int) and ret != 0:
            errcode = resp.get("errcode")
            errmsg = resp.get("errmsg")
            raise RuntimeError(f"sendmessage failed ret={ret} errcode={errcode} errmsg={errmsg}")
        return resp

