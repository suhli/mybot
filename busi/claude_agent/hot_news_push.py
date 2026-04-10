from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from busi.claude_agent.weixin_adapter import weixin_claude_run_config
from lib.claude.agent import format_reply_chunks, run_agent_reply_sync
from lib.claude.sessions import load_agent_sessions, save_agent_sessions
from lib.tasks.get_hot_news import run_get_hot_news
from lib.weixin_bot.daemon import PersonalWeixinDaemon

logger = logging.getLogger(__name__)

_HOT_PUSH_SESSION_KEY = "__hot_news_push__"


def _resolve_push_target_user(daemon: PersonalWeixinDaemon) -> str:
    explicit = os.environ.get("WEIXIN_NEWS_PUSH_TO", "").strip()
    if explicit:
        return explicit
    return str(daemon.session.user_id or "").strip()


def _build_json_analyze_prompt(snapshot_path: Path) -> str:
    # 通过明确指令触发 `newsnow-json-analyze` skill
    return (
        "请使用 `.claude/skills/newsnow-json-analyze/SKILL.md` 的规则，"
        "仅分析我提供的这个 JSON 文件，不要执行任何抓取任务。\n\n"
        f"JSON 文件路径: {snapshot_path.as_posix()}\n\n"
        "请输出：\n"
        "1) 文件类型判断与关键指标\n"
        "2) 标题分类统计\n"
        "3) 简短分析结论（主题/来源集中度/异常说明）"
    )


def build_hot_news_push_task(daemon: PersonalWeixinDaemon) -> Callable[[], None]:
    """
    定时任务入口：
    1) 抓取热文快照
    2) 若存在 `new_hot_count_vs_today_before` 增量，调用 Claude 分析该 JSON
    3) 将分析结果发到微信
    """
    sessions = load_agent_sessions()

    def task() -> None:
        snapshot_path = run_get_hot_news()
        try:
            raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("热文快照解析失败 path=%s err=%s", snapshot_path, exc)
            return

        if not isinstance(raw, dict):
            logger.warning("热文快照格式异常 path=%s", snapshot_path)
            return

        new_count = raw.get("new_hot_count_vs_today_before", 0)
        if not isinstance(new_count, int):
            new_count = 0
        if new_count <= 0:
            logger.info("热文无新增，跳过 Claude 分析与微信推送")
            return

        target_user = _resolve_push_target_user(daemon)
        if not target_user:
            logger.warning(
                "未配置推送目标用户：请设置 WEIXIN_NEWS_PUSH_TO 或确保登录会话有 user_id，当前跳过推送"
            )
            return

        cfg = weixin_claude_run_config()
        prompt = _build_json_analyze_prompt(snapshot_path)
        resume_id = sessions.get(_HOT_PUSH_SESSION_KEY)
        logger.info(
            "热文新增 %s 条，开始 Claude 分析并推送，target=%s path=%s",
            new_count,
            target_user,
            snapshot_path,
        )
        try:
            reply, new_session_id = run_agent_reply_sync(
                prompt,
                channel_user_id=target_user,
                resume_session_id=resume_id,
                config=cfg,
                session_slot_prefix="wx_hotnews",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude 热文分析失败: %s", exc)
            return

        if new_session_id:
            sessions[_HOT_PUSH_SESSION_KEY] = new_session_id
            save_agent_sessions(sessions)

        chunks = format_reply_chunks(reply, config=cfg)
        logger.info("Claude 热文分析完成，分片=%s", len(chunks))
        for chunk in chunks:
            daemon.send_text(target_user, chunk)

    return task

