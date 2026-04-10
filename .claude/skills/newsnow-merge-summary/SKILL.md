---
name: newsnow-merge-summary
description: >-
  仅调用 `.claude/skills/scripts/merge_snapshot_json.py` 合并 `ws/news` 或 `ws/hot-news` 某天目录下的 JSON，
  然后输出中文摘要；不执行 `run_get_latest_news` 或 `run_get_hot_news` 等抓取任务。
  在用户要“只基于已落盘快照做汇总/复盘”时使用。
---

# NewsNow 合并汇总（不抓取）

## 目的

只使用本地已有快照文件（`ws/news` 或 `ws/hot-news`）进行合并与摘要，**不触发任何抓取任务**。

## 适用场景

当用户提出以下诉求时使用本 skill：

- 只看某天已抓取结果的汇总
- 不想重新抓取，只想复盘本地快照
- 要快速得到 latest/hot 的日内合并统计

## 强约束

- 禁止调用：
  - `run_get_latest_news()`
  - `run_get_hot_news()`
- 仅可调用脚本：
  - `.claude/skills/scripts/merge_snapshot_json.py`

## 必须执行的流程

1. 确认用户要汇总的是：
   - latest（`ws/news/...`）或
   - hot（`ws/hot-news/...`）
2. 执行合并脚本（二选一）：
   - 指定日期目录：`--dir`
   - 自动最新日期：`--latest-day`
3. 读取脚本输出的 `merged.json`。
4. 输出中文摘要 + 分析，至少包含：
   - 合并时间 `merged_at`
   - 目标目录 `target_dir`
   - 文件数量 `file_count` / 记录数量 `record_count`
   - 汇总统计 `summary`
   - 标题分类统计（如可从源文件提取 title）
   - 简短分析结论（趋势、来源集中度、异常说明）
   - 若有错误，列出 `errors_by_file` 的关键项

## 执行参考

```bash
# latest：指定某天
python .claude/skills/scripts/merge_snapshot_json.py --dir ws/news/yyyy-mm-dd

# latest：自动最新一天
python .claude/skills/scripts/merge_snapshot_json.py --latest-day ws/news

# hot：指定某天
python .claude/skills/scripts/merge_snapshot_json.py --dir ws/hot-news/yyyy-mm-dd

# hot：自动最新一天
python .claude/skills/scripts/merge_snapshot_json.py --latest-day ws/hot-news
```

> 脚本 stdout 会返回合并后的 JSON 路径（默认 `<目标目录>/merged.json`）。

## 输出模板（中文）

```text
合并快照时间: <merged_at>
目标目录: <target_dir>
文件统计: 文件 <file_count> 个，成功解析 <record_count> 个

汇总统计:
- total_success_count: <value>
- total_error_count: <value>
- total_new_count_vs_before_today: <value>
- total_new_hot_count_vs_today_before: <value>

异常文件/来源:
- <file_or_source>: <error>

标题分类统计:
- 科技/产品: <count>
- 财经/市场: <count>
- 政策/时政: <count>
- 社区/论坛: <count>
- 影音/娱乐: <count>
- 其它: <count>

分析结论:
- 趋势判断: <一句话>
- 来源集中度: <一句话>
- 异常说明: <一句话，可无>
```

## 标题分类规则

按标题关键词做启发式分类（可多标签，但汇总时按首个命中标签计数）：

- 科技/产品：AI、模型、发布、开源、GitHub、软件、芯片、系统
- 财经/市场：股、基金、A股、美股、港股、融资、财报、市场、美元
- 政策/时政：政策、国务院、部委、监管、通告、国际、外交、战争
- 社区/论坛：V2EX、LinuxDo、帖子、讨论、问答、社区
- 影音/娱乐：电影、剧集、综艺、B站、抖音、视频、明星、音乐
- 其它：未命中上述关键词

## 注意事项

- 该 skill 的输入是“已有 JSON”，不是在线接口。
- 若目录不存在或没有 JSON，需直接说明原因并给出可执行命令示例。
- 摘要保持简洁、可读，优先给关键数字和异常信息。

