from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from .client import WeixinClient
from .models import DEFAULT_BASE_URL, DEFAULT_BOT_TYPE, Session
from .qr import print_qr_to_console
from .storage import load_context_tokens, load_session, save_context_tokens, save_session

logger = logging.getLogger(__name__)


class PersonalWeixinDaemon:
    def __init__(self) -> None:
        self.session = self._ensure_login()
        self.stop_event = threading.Event()
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.context_tokens: dict[str, str] = load_context_tokens()
        self._handlers: list[Callable[[dict[str, Any]], None]] = []

    def _ensure_login(self) -> Session:
        try:
            return load_session()
        except FileNotFoundError:
            return self._login_once()

    def _login_once(self) -> Session:
        client = WeixinClient(base_url=DEFAULT_BASE_URL, timeout=35.0)
        try:
            qr = client.get_bot_qrcode(bot_type=DEFAULT_BOT_TYPE)
            qrcode = str(qr.get("qrcode", "") or "")
            qrcode_url = str(qr.get("qrcode_img_content", "") or "")
            if not qrcode or not qrcode_url:
                raise RuntimeError("获取二维码失败")
            logger.info("请使用微信扫码登录（控制台二维码如下）:")
            print_qr_to_console(qrcode_url)
            logger.info("若二维码显示异常，请打开: %s", qrcode_url)
            deadline = time.time() + 480
            while time.time() < deadline:
                status = client.get_qrcode_status(qrcode=qrcode)
                s = str(status.get("status", "wait"))
                if s == "confirmed":
                    bot_token = status.get("bot_token")
                    bot_id = status.get("ilink_bot_id")
                    if not bot_token or not bot_id:
                        raise RuntimeError("登录成功但缺少 bot_token 或 ilink_bot_id")
                    session = Session(
                        bot_token=str(bot_token),
                        bot_id=str(bot_id),
                        user_id=status.get("ilink_user_id"),
                        base_url=str(status.get("baseurl") or DEFAULT_BASE_URL),
                    )
                    save_session(session)
                    logger.info("登录成功，bot_id=%s", session.bot_id)
                    return session
                if s == "scaned":
                    logger.info("已扫码，请在手机确认...")
                elif s == "expired":
                    raise RuntimeError("二维码已过期，请重启进程重新登录")
                time.sleep(1.0)
            raise RuntimeError("登录超时")
        finally:
            client.close()

    def _extract_text(self, msg: dict[str, Any]) -> str:
        for item in msg.get("item_list", []) or []:
            if item.get("type") == 1:
                return (item.get("text_item") or {}).get("text", "")
        return ""

    def add_message_handler(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """注册消息处理回调: handler(event: dict) -> None"""
        self._handlers.append(handler)

    def send_text(self, to_user_id: str, text: str, context_token: str = "") -> None:
        if not to_user_id:
            raise RuntimeError("to_user_id 不能为空")
        token = context_token or self.context_tokens.get(to_user_id, "")
        if not token:
            logger.warning("send_text: to=%s 缺少 context_token，可能导致微信侧不展示消息", to_user_id)
        client = WeixinClient(base_url=self.session.base_url, timeout=15.0)
        try:
            resp = client.send_text(
                token=self.session.bot_token,
                to_user_id=to_user_id,
                text=text,
                context_token=token,
            )
            logger.info("send_text done: to=%s resp=%s", to_user_id, resp)
        finally:
            client.close()

    def _poll_loop(self) -> None:
        while not self.stop_event.is_set():
            client = WeixinClient(base_url=self.session.base_url, timeout=35.0)
            try:
                resp = client.get_updates(
                    token=self.session.bot_token,
                    get_updates_buf=self.session.get_updates_buf,
                )
            except Exception as exc:
                logger.warning("拉取消息失败: %s", exc)
                time.sleep(1.5)
                continue
            finally:
                client.close()

            self.session.get_updates_buf = resp.get("get_updates_buf", self.session.get_updates_buf)
            save_session(self.session)
            for msg in resp.get("msgs", []) or []:
                from_user = str(msg.get("from_user_id", "") or "")
                context_token = str(msg.get("context_token", "") or "")
                text = self._extract_text(msg)
                if from_user and context_token:
                    self.context_tokens[from_user] = context_token
                    save_context_tokens(self.context_tokens)
                logger.info("INBOUND from=%s text=%s", from_user, text)
                event = {
                    "from_user_id": from_user,
                    "text": text,
                    "context_token": context_token,
                    "raw": msg,
                }
                for handler in self._handlers:
                    try:
                        handler(event)
                    except Exception as exc:
                        logger.exception("handler 执行失败")

            time.sleep(0.2)

    def start(self) -> None:
        if self.poll_thread.is_alive():
            return
        self.poll_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.poll_thread.is_alive():
            self.poll_thread.join(timeout=2.0)

    def run_forever(self) -> None:
        logger.info("常驻服务启动成功（单账号）。")
        logger.info("可在同一进程内注册 handler，并在 handler 或定时任务中调用 send_text。")
        self.start()
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("收到退出信号，正在停止...")
        finally:
            self.stop()


def run() -> None:
    daemon = PersonalWeixinDaemon()
    daemon.run_forever()

