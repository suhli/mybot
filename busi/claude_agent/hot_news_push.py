from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable

from busi.claude_agent.weixin_adapter import weixin_claude_run_config
from lib.claude.agent import format_reply_chunks, run_agent_reply_sync
from lib.tasks.get_hot_news import run_get_hot_news
from lib.weixin_bot.daemon import PersonalWeixinDaemon

logger = logging.getLogger(__name__)


def _resolve_push_target_user(daemon: PersonalWeixinDaemon) -> str:
    explicit = os.environ.get("WEIXIN_NEWS_PUSH_TO", "").strip()
    if explicit:
        return explicit
    return str(daemon.session.user_id or "").strip()


def _build_json_analyze_prompt(snapshot_path: Path) -> str:
    """读者向热文汇总：调用 newsnow-json-analyze 处理 hot 快照，输出主题归纳与代表条目。"""
    return (
        "调用 skill `.claude/skills/newsnow-json-analyze/SKILL.md` 分析下列 hot 类型快照，"
        "不抓取、不改写文件。\n"
        f"JSON 路径: {snapshot_path.as_posix()}\n\n"
        "输出要求（中文，可直接发微信）：\n"
        "- 首行：生成时间 + 本轮相对今日已落盘快照的新增热文条数。\n"
        "- 正文：按主题归纳今日热点（3~6 个主题），每个主题 1~2 句概括，"
        "再附 1~3 条最具代表性的标题 + URL；不要罗列全部新增。\n"
        "- 末尾 1~2 句总结今日基调；有失败来源仅用一行列出来源 ID。\n"
        "- 禁止输出「文件类型判断」「分类统计表」「核心指标」等元信息，语气紧凑。"
    )


def build_hot_news_push_task(daemon: PersonalWeixinDaemon) -> Callable[[], None]:
    """
    定时任务入口：
    1) 抓取热文快照
    2) 若存在 `new_hot_count_vs_today_before` 增量，调用 Claude 根据该 JSON 生成热文汇总
    3) 将汇总文本发到微信

    每次都使用一个新的 Claude 会话，不复用 resume id。
    """

    def task() -> None:
        try:
            snapshot_path = run_get_hot_news()
        except Exception as exc:  # noqa: BLE001
            logger.warning("抓取热文快照失败: %s", exc)
            return

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
                "未配置推送目标用户：设置 WEIXIN_NEWS_PUSH_TO 或确保登录会话有 user_id，跳过本次推送"
            )
            return

        cfg = weixin_claude_run_config()
        prompt = _build_json_analyze_prompt(snapshot_path)
        logger.info(
            "热文新增 %s 条，开始 Claude 汇总并推送，target=%s path=%s",
            new_count,
            target_user,
            snapshot_path,
        )
        try:
            reply, _ = run_agent_reply_sync(
                prompt,
                channel_user_id=target_user,
                resume_session_id=None,
                config=cfg,
                session_slot_prefix="wx_hotnews",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude 热文汇总失败: %s", exc)
            return

        chunks = format_reply_chunks(reply, config=cfg)
        logger.info("Claude 热文汇总完成，分片=%s", len(chunks))
        for chunk in chunks:
            daemon.send_text(target_user, chunk)

    return task

