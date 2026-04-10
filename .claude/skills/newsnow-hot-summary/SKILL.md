---
name: newsnow-hot-summary
description: >-
  执行 `run_get_hot_news`，在 `ws/hot-news` 下定位最新快照 JSON，并输出简明中文热文摘要（生成时间、成功/失败数、
  各来源热文数量、热文标题与链接、失败来源 ID）。
  在用户要 NewsNow 热文汇总、本轮热榜简报、或基于仓库已抓取热文的快速文字总结时使用。
---

# NewsNow 热文摘要

## 目的

调用现有的 `run_get_hot_news` 任务，然后读取最新生成的 JSON 文件，并输出简明中文热文摘要。

## 适用场景

当用户提出以下诉求时使用本 skill：

- 要最新热文/热榜汇总
- 要本轮热文抓取简报
- 要按来源快速浏览当前热点

## 必须执行的流程

1. 执行 `lib.tasks.get_hot_news` 中的 `run_get_hot_news()`。
2. 在 `ws/hot-news/yyyy-mm-dd/*.json` 中按修改时间找到最新快照文件。
3. 读取该 JSON。
4. 输出中文摘要，至少包含：
   - 生成时间
   - 成功数 / 失败数
   - 按来源分组的热文数量（优先使用 `hot_count_by_source`）
   - 每个来源列出最多 3 条热文（`title + url`）
   - 若存在错误，列出失败来源 ID

## 执行参考

可使用以下方式：

- Python 内联执行：

```python
from lib.tasks.get_hot_news import run_get_hot_news
path = run_get_hot_news()
print(path)
```

- 然后读取文件并汇总字段：
  - `generated_at`
  - `success_count`
  - `error_count`
  - `hot_items_per_source_limit`
  - `hot_count_by_source`
  - `hot_items_by_source`
  - `errors`

## 结果产出位置

- 原始抓取结果（JSON）保存到：
  - `ws/hot-news/yyyy-mm-dd/hh_mm_ss.json`
- `run_get_hot_news()` 的返回值就是本次生成的 JSON 文件路径。
- 若需要“最新一份结果”，应在 `ws/hot-news` 下按文件修改时间取最新 `.json`。
- 本 skill 的“总结文本”默认输出到当前对话回复（或控制台标准输出）；除非用户明确要求，不额外落盘文本文件。

## 输出模板（中文）

```text
热文快照时间: <generated_at>
抓取结果: 成功 <success_count>，失败 <error_count>

按来源热文:
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
- 如果 `hot_items_by_source` 为空，需要明确说明“当前未抓取到可展示热文”。
- 摘要时优先按来源组织，不要只给混合列表。
- 摘要保持简洁、清晰、可读。

