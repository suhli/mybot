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


def _item_key(source_id: str, item: dict[str, Any]) -> str:
    item_id = str(item.get("id", "") or "")
    url = str(item.get("url", "") or "")
    title = str(item.get("title", "") or "")
    return f"{source_id}::{item_id}::{url}::{title}"


def _normalize_item(source_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "id": item.get("id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "mobileUrl": item.get("mobileUrl"),
        "pubDate": item.get("pubDate"),
    }


def _collect_history_keys_today_before(out_dir: Path, out_file: Path) -> set[str]:
    keys: set[str] = set()
    if not out_dir.exists():
        return keys

    for snapshot_file in out_dir.glob("*.json"):
        if snapshot_file.name >= out_file.name:
            continue
        try:
            raw = json.loads(snapshot_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if not isinstance(raw, dict):
            continue
        # 兼容历史字段：优先 hot_items_by_source，其次 results.items
        hot_items_by_source = raw.get("hot_items_by_source")
        if isinstance(hot_items_by_source, dict):
            for source_id, items in hot_items_by_source.items():
                if not isinstance(source_id, str) or not isinstance(items, list):
                    continue
                for item in items:
                    if isinstance(item, dict):
                        keys.add(_item_key(source_id, item))
            continue

        results = raw.get("results", {})
        if not isinstance(results, dict):
            continue
        for source_id, payload in results.items():
            if not isinstance(source_id, str) or not isinstance(payload, dict):
                continue
            items = payload.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if isinstance(item, dict):
                    keys.add(_item_key(source_id, item))
    return keys


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
    history_keys = _collect_history_keys_today_before(out_dir=out_dir, out_file=out_file)
    new_hot_items_by_source: dict[str, list[dict[str, Any]]] = {}
    for source_id, items in hot_items_by_source.items():
        new_items = [item for item in items if _item_key(source_id, item) not in history_keys]
        if new_items:
            new_hot_items_by_source[source_id] = new_items
    new_hot_count_by_source = {
        source_id: len(items) for source_id, items in new_hot_items_by_source.items()
    }
    new_hot_items = [item for items in new_hot_items_by_source.values() for item in items]

    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "base_url": "https://newsnow.busiyi.world",
        "source_count": len(SOURCE_IDS),
        "success_count": len(all_results),
        "error_count": len(errors),
        "hot_items_per_source_limit": HOT_ITEMS_PER_SOURCE,
        "hot_count_by_source": hot_count_by_source,
        "hot_items_by_source": hot_items_by_source,
        "new_hot_count_vs_today_before": len(new_hot_items),
        "new_hot_count_by_source": new_hot_count_by_source,
        "new_hot_items_by_source": new_hot_items_by_source,
        "new_hot_items": new_hot_items,
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
    logger.info("相对今日已生成快照的新增热文: %s", len(new_hot_items))
    return out_file

