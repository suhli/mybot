#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge all JSON snapshots under a directory."
    )
    parser.add_argument(
        "--dir",
        default="",
        help="Snapshot directory, e.g. ws/news/2026-04-10 or ws/hot-news/2026-04-10",
    )
    parser.add_argument(
        "--latest-day",
        default="",
        help="Base directory to auto-pick latest date dir, e.g. ws/news or ws/hot-news",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output path. Default: <dir>/merged.json",
    )
    return parser.parse_args()


def _safe_int(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _resolve_target_dir(dir_arg: str, latest_day_arg: str) -> Path | None:
    if dir_arg and latest_day_arg:
        return None
    if dir_arg:
        return Path(dir_arg)
    if latest_day_arg:
        base = Path(latest_day_arg)
        if not base.exists() or not base.is_dir():
            return None
        day_dirs = sorted([p for p in base.iterdir() if p.is_dir() and p.name[:4].isdigit()])
        if not day_dirs:
            return None
        return day_dirs[-1]
    return None


def _iter_source_items(raw: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    从快照中提取“按来源分组的条目列表”。
    兼容 news / hot-news 的常见字段。
    """
    candidate_keys = (
        "new_items_by_source",
        "hot_items_by_source",
        "new_hot_items_by_source",
        "items_by_source",
    )
    for key in candidate_keys:
        value = raw.get(key)
        if not isinstance(value, dict):
            continue
        out: list[tuple[str, list[dict[str, Any]]]] = []
        for source_id, items in value.items():
            if not isinstance(source_id, str) or not isinstance(items, list):
                continue
            typed_items = [it for it in items if isinstance(it, dict)]
            out.append((source_id, typed_items))
        if out:
            return out
    return []


def _normalize_title(title: str) -> str:
    return " ".join(title.split()).strip()


def main() -> int:
    args = _parse_args()
    target_dir = _resolve_target_dir(args.dir, args.latest_day)
    if target_dir is None:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "use exactly one of --dir or --latest-day, and ensure target exists",
                },
                ensure_ascii=False,
            )
        )
        return 1
    if not target_dir.exists() or not target_dir.is_dir():
        print(json.dumps({"ok": False, "error": f"invalid dir: {target_dir}"}, ensure_ascii=False))
        return 1

    output_path = Path(args.output) if args.output else target_dir / "merged.json"
    files = sorted(
        file for file in target_dir.glob("*.json") if file.resolve() != output_path.resolve()
    )
    if not files:
        print(json.dumps({"ok": False, "error": f"no json files in: {target_dir}"}, ensure_ascii=False))
        return 1

    records: list[dict[str, Any]] = []
    total_success = 0
    total_error = 0
    total_new = 0
    total_new_hot = 0
    merged_errors: dict[str, dict[str, str]] = {}
    title_index: dict[str, dict[str, Any]] = {}
    title_empty_count = 0

    for file in files:
        try:
            raw = json.loads(file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            merged_errors[file.name] = {"__file__": f"read_failed: {exc}"}
            continue

        if not isinstance(raw, dict):
            merged_errors[file.name] = {"__file__": "invalid_json_root"}
            continue

        success_count = _safe_int(raw.get("success_count"))
        error_count = _safe_int(raw.get("error_count"))
        new_count = _safe_int(raw.get("new_count_vs_before_today"))
        new_hot_count = _safe_int(raw.get("new_hot_count_vs_today_before"))

        total_success += success_count
        total_error += error_count
        total_new += new_count
        total_new_hot += new_hot_count

        file_errors = raw.get("errors", {})
        if isinstance(file_errors, dict) and file_errors:
            merged_errors[file.name] = {
                str(k): str(v) for k, v in file_errors.items()
            }

        source_items = _iter_source_items(raw)
        for source_id, items in source_items:
            for item in items:
                title_raw = item.get("title")
                if not isinstance(title_raw, str):
                    continue
                title = _normalize_title(title_raw)
                if not title:
                    title_empty_count += 1
                    continue
                url = item.get("url")
                url_text = url if isinstance(url, str) else ""
                key = title.lower()
                bucket = title_index.setdefault(
                    key,
                    {
                        "title": title,
                        "sources": set(),
                    },
                )
                bucket["sources"].add(source_id)

        records.append(
            {
                "file": file.name,
                "generated_at": raw.get("generated_at"),
                "success_count": success_count,
                "error_count": error_count,
                "new_count_vs_before_today": new_count,
                "new_hot_count_vs_today_before": new_hot_count,
                "source_count": _safe_int(raw.get("source_count")),
            }
        )

    titles_merged: list[dict[str, Any]] = []
    for item in title_index.values():
        titles_merged.append(
            {
                "title": item["title"],
                "sources": sorted(item["sources"]),
            }
        )
    titles_merged.sort(key=lambda x: str(x["title"]))

    output = {
        "merged_at": datetime.now().isoformat(timespec="seconds"),
        "target_dir": str(target_dir),
        "file_count": len(files),
        "record_count": len(records),
        "summary": {
            "total_success_count": total_success,
            "total_error_count": total_error,
            "total_new_count_vs_before_today": total_new,
            "total_new_hot_count_vs_today_before": total_new_hot,
            "total_unique_titles": len(titles_merged),
            "empty_title_count": title_empty_count,
        },
        "records": records,
        "titles_merged": titles_merged,
        "errors_by_file": merged_errors,
    }

    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

