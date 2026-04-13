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
    """要的是读者向热文汇总（标题+链接+短评），不是对 JSON/任务的元数据分析简报。"""
    return (
        "请阅读下列热文快照 JSON，不要执行任何抓取、不要改写文件。"
        "字段含义与结构可参考 `.claude/skills/newsnow-json-analyze/SKILL.md`，"
        "但输出必须是「给微信好友看的新闻汇总」，禁止写成对任务的简报或数据分析报告。\n\n"
        f"JSON 文件路径: {snapshot_path.as_posix()}\n\n"
        "用中文输出，格式与内容要求：\n"
        "- 开头一行：快照生成时间；若有 `new_hot_count_vs_today_before`，写明本轮相对今日已落盘快照的新增热文条数。\n"
        "- 正文：按来源分段；优先写 `new_hot_items` / `new_hot_items_by_source` 里的新增，"
        "不足再补 `hot_items_by_source`。每条一行或一小段：清晰标题 + 完整可点击 URL。\n"
        "- 结尾 2～4 句：概括今天热点在聊什么（主题/方向即可），像编辑导语，不要提「JSON」「文件类型」「结构」。\n"
        "- 禁止输出「文件类型判断」「标题分类统计表」「核心指标」等大段元信息；"
        "成功/失败数若存在，最多用一行带过；有失败来源时文末列出对应来源 ID 即可。\n"
        "- 语气紧凑、可直接复制发送，避免空话套话。"
    )


def build_hot_news_push_task(daemon: PersonalWeixinDaemon) -> Callable[[], None]:
    """
    定时任务入口：
    1) 抓取热文快照
    2) 若存在 `new_hot_count_vs_today_before` 增量，调用 Claude 根据该 JSON 生成热文汇总
    3) 将汇总文本发到微信
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
            logger.info("热文无新增，跳过 Claude 汇总与微信推送")
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
            "热文新增 %s 条，开始 Claude 汇总并推送，target=%s path=%s",
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
            logger.warning("Claude 热文汇总失败: %s", exc)
            return

        if new_session_id:
            sessions[_HOT_PUSH_SESSION_KEY] = new_session_id
            save_agent_sessions(sessions)

        chunks = format_reply_chunks(reply, config=cfg)
        logger.info("Claude 热文汇总完成，分片=%s", len(chunks))
        for chunk in chunks:
            daemon.send_text(target_user, chunk)

    return task

