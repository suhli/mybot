---
name: newsnow-latest-summary
description: >-
  执行 `run_get_latest_news`，在 `ws/news` 下定位最新快照 JSON，并输出简明中文摘要（生成时间、成功/失败数、
  `new_count_vs_before_today`、按来源的新增标题与链接、失败来源 ID）。
  在用户要 NewsNow 快照摘要、本轮抓取简报、或基于仓库已抓取新闻的快速文字汇总时使用。
---

# NewsNow 最新摘要

## 目的

调用现有的 `run_get_latest_news` 任务，然后读取最新生成的 JSON 文件，并输出简明中文摘要。

## 适用场景

当用户提出以下诉求时使用本 skill：

- 要最新 NewsNow 快照摘要
- 要本轮抓取更新简报
- 要快速文本版新闻更新摘要

## 必须执行的流程

1. 执行 `lib.tasks.get_latest_news` 中的 `run_get_latest_news()`。
2. 在 `ws/news/yyyy-mm-dd/*.json` 中按修改时间找到最新快照文件。
3. 读取该 JSON。
4. 输出中文摘要，至少包含：
   - 生成时间
   - 成功数 / 失败数
   - `new_count_vs_before_today`
   - 按来源分组的新增数量（优先使用 `new_count_by_source`）
   - 每个来源列出最多 3 条新增（`title + url`）
   - 若存在错误，列出失败来源 ID

## 执行参考

可使用以下方式：

- Python 内联执行：

```python
from lib.tasks.get_latest_news import run_get_latest_news
path = run_get_latest_news()
print(path)
```

- 然后读取文件并汇总字段：
  - `generated_at`
  - `success_count`
  - `error_count`
  - `new_count_vs_before_today`
  - `new_count_by_source`
  - `new_items_by_source`
  - `new_items`
  - `errors`

## 结果产出位置

- 原始抓取结果（JSON）保存到：
  - `ws/news/yyyy-mm-dd/hh_mm_ss.json`
- `run_get_latest_news()` 的返回值就是本次生成的 JSON 文件路径。
- 若需要“最新一份结果”，应在 `ws/news` 下按文件修改时间取最新 `.json`。
- 本 skill 的“总结文本”默认输出到当前对话回复（或控制台标准输出）；除非用户明确要求，不额外落盘文本文件。

## 输出模板（中文）

```text
新闻快照时间: <generated_at>
抓取结果: 成功 <success_count>，失败 <error_count>
相对今天之前新增: <new_count_vs_before_today>

按来源新增:
- <source_id>: <count> 条
  1) <title>
     <url>
  2) <title>
     <url>

失败来源:
- <source_id>: <error_message>
```

## 注意事项

- 优先使用本次执行后最新生成的 JSON 文件。
- 如果 `new_items` 为空，需要明确说明“未发现相对历史的新增新闻”。
- 摘要时优先按来源组织，不要只给混合列表。
- 摘要保持简洁、清晰、可读。

