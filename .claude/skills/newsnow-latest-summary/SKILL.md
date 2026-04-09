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

