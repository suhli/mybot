from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.newsnow_client import NewsNowClient, NewsNowError
from lib.tasks.get_latest_news import FETCH_SLEEP_SEC, SOURCE_IDS

logger = logging.getLogger(__name__)

HOT_ITEMS_PER_SOURCE = 10


def _normalize_item(source_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "mobileUrl": item.get("mobileUrl"),
        "pubDate": item.get("pubDate"),
    }


def run_get_hot_news() -> Path:
    """
    抓取各来源当前热文（不做历史新增对比）。
    输出目录: ws/hot-news/YYYY-MM-DD/HH_MM_SS.json
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%H_%M_%S")

    ws_hot_dir = Path("ws") / "hot-news"
    out_dir = ws_hot_dir / today
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ts}.json"

    all_results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    logger.info("开始抓取热文，共 %s 个来源...", len(SOURCE_IDS))
    with NewsNowClient() as client:
        for i, source_id in enumerate(SOURCE_IDS):
            try:
                all_results[source_id] = client.get_source(source_id=source_id, latest=False)
            except NewsNowError as exc:
                logger.warning("来源 %s 抓取失败: %s", source_id, exc)
                errors[source_id] = "fetch_failed"
            except Exception as exc:  # noqa: BLE001
                logger.warning("来源 %s 抓取异常: %s", source_id, exc)
                errors[source_id] = "unexpected_error"
            if i + 1 < len(SOURCE_IDS):
                time.sleep(FETCH_SLEEP_SEC)

    hot_items_by_source: dict[str, list[dict[str, Any]]] = {}
    for source_id, payload in all_results.items():
        if not isinstance(payload, dict):
            continue
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue
        normalized = [
            _normalize_item(source_id, item)
            for item in items
            if isinstance(item, dict)
        ]
        if normalized:
            hot_items_by_source[source_id] = normalized[:HOT_ITEMS_PER_SOURCE]

    hot_count_by_source = {
        source_id: len(items) for source_id, items in hot_items_by_source.items()
    }

    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "base_url": "https://newsnow.busiyi.world",
        "source_count": len(SOURCE_IDS),
        "success_count": len(all_results),
        "error_count": len(errors),
        "hot_items_per_source_limit": HOT_ITEMS_PER_SOURCE,
        "hot_count_by_source": hot_count_by_source,
        "hot_items_by_source": hot_items_by_source,
        "errors": errors,
        "results": all_results,
    }
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("热文快照已保存: %s", out_file)
    logger.info("成功: %s | 失败: %s", len(all_results), len(errors))
    if errors:
        logger.warning("以下 %s 个来源抓取失败，原因如下:", len(errors))
        for source_id, err_code in sorted(errors.items()):
            logger.warning("  %s: %s", source_id, err_code)
    logger.info("热文来源数: %s", len(hot_items_by_source))
    return out_file

