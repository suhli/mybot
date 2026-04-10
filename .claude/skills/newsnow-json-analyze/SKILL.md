---
name: newsnow-json-analyze
description: >-
  对用户指定的 NewsNow JSON 文件做分析（支持 latest/hot/merged 三种结构），输出中文汇总、
  标题分类统计与结论；不触发抓取任务。用于“给定 JSON 路径直接分析”的场景。
---

# NewsNow 指定 JSON 分析

## 目的

对用户明确指定的 JSON 文件路径直接分析并给出中文报告，不执行抓取任务。

## 适用场景

当用户提出以下诉求时使用本 skill：

- 指定某个 JSON 文件让你分析
- 对单份快照做总结、分类、结论
- 只看离线文件，不跑任何在线抓取

## 强约束

- 禁止调用：
  - `run_get_latest_news()`
  - `run_get_hot_news()`
- 禁止自行改写原始 JSON 内容。

## 必须执行的流程

1. 确认用户给出的 JSON 文件路径。
2. 读取 JSON 并识别结构类型：
   - latest 快照（含 `new_items` / `new_items_by_source`）
   - hot 快照（含 `hot_items_by_source` / `new_hot_items`）
   - merged 汇总（含 `records` / `summary`）
3. 提取可分析标题集合（优先顺序）：
   - `new_items`
   - `new_hot_items`
   - `hot_items_by_source[*]`
   - `new_items_by_source[*]`
4. 输出中文分析，至少包含：
   - 文件类型判断 + 关键元信息（`generated_at` 或 `merged_at`）
   - 成功/失败指标（若存在）
   - 来源维度概览（若存在）
   - 标题分类统计
   - 结论（主题、来源集中度、异常说明）

## 输出模板（中文）

```text
文件路径: <path>
文件类型: <latest|hot|merged|unknown>
时间: <generated_at 或 merged_at>

核心指标:
- 成功: <success_count 或 total_success_count>
- 失败: <error_count 或 total_error_count>
- 来源数: <source_count 或可推导值>

标题分类统计:
- 科技/产品: <count>
- 财经/市场: <count>
- 政策/时政: <count>
- 社区/论坛: <count>
- 影音/娱乐: <count>
- 其它: <count>

结论:
- 主题观察: <一句话>
- 来源分布: <一句话>
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

- 若 JSON 字段缺失，要在报告中说明“字段缺失，按可用字段分析”。
- 若标题集合为空，要明确说明“无可分类标题”。
- 保持结果简洁，优先关键数字与结论。

