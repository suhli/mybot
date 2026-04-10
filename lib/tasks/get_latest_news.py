from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.newsnow_client import NewsNowClient, NewsNowError

logger = logging.getLogger(__name__)

# 连续请求间隔（秒），减轻限流/HTML 拦截
FETCH_SLEEP_SEC = 0.8

SOURCE_IDS: list[str] = [
    "zhihu",
    "weibo",
    "zaobao",
    "coolapk",
    "douyin",
    "hupu",
    "tieba",
    "toutiao",
    "ithome",
    "thepaper",
    "sputniknewscn",
    "cankaoxiaoxi",
    "gelonghui",
    "solidot",
    "hackernews",
    "producthunt",
    "kaopu",
    "jin10",
    "baidu",
    "nowcoder",
    "sspai",
    "juejin",
    "ifeng",
    "douban",
    "steam",
    "freebuf",
    "v2ex",
    "mktnews",
    "wallstreetcn",
    "36kr",
    "pcbeta",
    "cls",
    "xueqiu",
    "fastbull",
    "github",
    "bilibili",
    "chongbuluo",
    "tencent",
    "qqvideo",
    "iqiyi",
    "v2ex-share",
    "mktnews-flash",
    "wallstreetcn-quick",
    "wallstreetcn-news",
    "wallstreetcn-hot",
    "36kr-quick",
    "36kr-renqi",
    "pcbeta-windows11",
    "cls-telegraph",
    "cls-depth",
    "cls-hot",
    "xueqiu-hotstock",
    "fastbull-express",
    "fastbull-news",
    "github-trending-today",
    "chongbuluo-latest",
    "chongbuluo-hot",
    "tencent-hot",
    "qqvideo-tv-hotsearch",
    "iqiyi-hot-ranklist",
]


def _item_key(source_id: str, item: dict[str, Any]) -> str:
    item_id = str(item.get("id", "") or "")
    url = str(item.get("url", "") or "")
    title = str(item.get("title", "") or "")
    return f"{source_id}::{item_id}::{url}::{title}"


def _collect_history_keys(ws_news_dir: Path, today: str) -> set[str]:
    keys: set[str] = set()
    if not ws_news_dir.exists():
        return keys

    for date_dir in ws_news_dir.iterdir():
        if not date_dir.is_dir():
            continue
        if date_dir.name >= today:
            continue

        for snapshot_file in date_dir.glob("*.json"):
            try:
                raw = json.loads(snapshot_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(raw, dict):
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


def run_get_latest_news() -> Path:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%H_%M_%S")

    ws_news_dir = Path("ws") / "news"
    out_dir = ws_news_dir / today
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ts}.json"

    all_results: dict[str, Any] = {}
    errors: dict[str, str] = {}

    logger.info("开始抓取，共 %s 个来源...", len(SOURCE_IDS))
    with NewsNowClient() as client:
        for i, source_id in enumerate(SOURCE_IDS):
            try:
                all_results[source_id] = client.get_source(source_id=source_id, latest=True)
            except NewsNowError as exc:
                errors[source_id] = str(exc)
            except Exception as exc:  # noqa: BLE001
                errors[source_id] = f"Unexpected error: {exc}"
            if i + 1 < len(SOURCE_IDS):
                time.sleep(FETCH_SLEEP_SEC)

    history_keys = _collect_history_keys(ws_news_dir=ws_news_dir, today=today)

    new_items: list[dict[str, Any]] = []
    new_items_by_source: dict[str, list[dict[str, Any]]] = {}
    for source_id, payload in all_results.items():
        if not isinstance(payload, dict):
            continue
        items = payload.get("items", [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            key = _item_key(source_id, item)
            if key not in history_keys:
                normalized_item = {
                    "source_id": source_id,
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "mobileUrl": item.get("mobileUrl"),
                    "pubDate": item.get("pubDate"),
                }
                new_items.append(normalized_item)
                if source_id not in new_items_by_source:
                    new_items_by_source[source_id] = []
                new_items_by_source[source_id].append(normalized_item)

    new_count_by_source = {
        source_id: len(items) for source_id, items in new_items_by_source.items()
    }

    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "base_url": "https://newsnow.busiyi.world",
        "source_count": len(SOURCE_IDS),
        "success_count": len(all_results),
        "error_count": len(errors),
        "new_count_vs_before_today": len(new_items),
        "new_count_by_source": new_count_by_source,
        "new_items_by_source": new_items_by_source,
        "errors": errors,
        "new_items": new_items,
        "results": all_results,
    }
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("已保存快照: %s", out_file)
    logger.info("成功: %s | 失败: %s", len(all_results), len(errors))
    if errors:
        logger.warning("以下 %s 个来源抓取失败，原因如下:", len(errors))
        for source_id, err_msg in sorted(errors.items()):
            logger.warning("  %s: %s", source_id, err_msg)
    logger.info("相对今天之前的新增新闻: %s", len(new_items))
    return out_file

