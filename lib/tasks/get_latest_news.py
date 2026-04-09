from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.newsnow_client import NewsNowClient, NewsNowError

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
    "linuxdo",
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
    "bilibili-hot-search",
    "bilibili-hot-video",
    "bilibili-ranking",
    "linuxdo-latest",
    "linuxdo-hot",
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

    print(f"[get_latest_news] 开始抓取，共 {len(SOURCE_IDS)} 个来源...")
    with NewsNowClient() as client:
        for source_id in SOURCE_IDS:
            try:
                all_results[source_id] = client.get_source(source_id=source_id, latest=True)
            except NewsNowError as exc:
                errors[source_id] = str(exc)
            except Exception as exc:  # noqa: BLE001
                errors[source_id] = f"Unexpected error: {exc}"

    history_keys = _collect_history_keys(ws_news_dir=ws_news_dir, today=today)

    new_items: list[dict[str, Any]] = []
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
                new_items.append(
                    {
                        "source_id": source_id,
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "mobileUrl": item.get("mobileUrl"),
                        "pubDate": item.get("pubDate"),
                    }
                )

    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "base_url": "https://newsnow.busiyi.world",
        "source_count": len(SOURCE_IDS),
        "success_count": len(all_results),
        "error_count": len(errors),
        "new_count_vs_before_today": len(new_items),
        "errors": errors,
        "new_items": new_items,
        "results": all_results,
    }
    out_file.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[get_latest_news] 已保存快照: {out_file}")
    print(f"[get_latest_news] 成功: {len(all_results)} | 失败: {len(errors)}")
    print(f"[get_latest_news] 相对今天之前的新增新闻: {len(new_items)}")
    return out_file

