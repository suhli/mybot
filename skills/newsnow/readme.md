# newsnow API 文档（公开无登录版）

基于仓库当前实现整理。  
本文档仅保留：

- 无需登录即可访问
- 且不属于登录流程本身

的接口。

## 基本说明

- 基础路径：`/api`
- 核心新闻接口：`/api/s`
- 批量缓存接口：`/api/s/entire`
- MCP 入口：`/api/mcp`

---

## 1. 获取版本信息

### `GET /api/latest`

返回当前版本号。

#### 请求示例

```bash
curl /api/latest
````

#### 响应示例

```json
{
  "v": "x.y.z"
}
```

---

## 2. 获取单个新闻源数据

### `GET /api/s`

获取单个新闻源数据，是项目最核心的接口。

#### 请求参数

| 参数       | 类型             | 必填 | 说明                          |
| -------- | -------------- | -- | --------------------------- |
| `id`     | string         | 是  | 新闻源 ID                      |
| `latest` | boolean/string | 否  | 传入后倾向于拉取较新数据，但是否真正强刷受缓存逻辑影响 |

#### 请求示例

```bash
curl "/api/s?id=hackernews"
curl "/api/s?id=zhihu&latest=true"
```

#### 响应示例

```json
{
  "status": "success",
  "id": "hackernews",
  "updatedTime": 1712345678901,
  "items": [
    {
      "id": "123",
      "title": "Example title",
      "url": "https://example.com",
      "mobileUrl": "https://m.example.com",
      "pubDate": 1712345600000,
      "extra": {
        "info": "附加信息"
      }
    }
  ]
}
```

#### 字段说明

##### 顶层字段

| 字段            | 类型     | 说明                      |
| ------------- | ------ | ----------------------- |
| `status`      | string | 通常为 `success` 或 `cache` |
| `id`          | string | 当前新闻源 ID                |
| `updatedTime` | number | 更新时间戳（毫秒）               |
| `items`       | array  | 新闻条目列表                  |

##### `items[]` 字段

| 字段          | 类型     | 说明       |
| ----------- | ------ | -------- |
| `id`        | string | 条目 ID    |
| `title`     | string | 标题       |
| `url`       | string | 链接       |
| `mobileUrl` | string | 移动端链接，可选 |
| `pubDate`   | number | 发布时间戳，可选 |
| `extra`     | object | 附加信息，可选  |

#### 说明

* `id` 无效时会报错
* 部分源可能存在重定向逻辑
* 命中较新缓存时，即使未重新抓取，也可能直接返回 `status: "success"`
* 抓取结果最多保留 30 条
* 抓取失败但旧缓存还在时，可能回退返回缓存结果

---

## 3. 新闻源 ID 列表

### 3.1 说明

项目里的源分两类：

1. **可直接请求的普通源**
2. **带子源的父级源**

如果某个父级源带有 `sub`，那么：

* 父级 ID 本身也能请求
* 但通常会自动重定向到第一个子源
* 更推荐直接请求具体子源 ID

例如：

* `v2ex` 会跳到 `v2ex-share`
* `wallstreetcn` 会跳到 `wallstreetcn-quick`

---

### 3.2 普通源 ID（可直接请求）

这些源没有子源，直接使用即可：

| ID              | 名称           |
| --------------- | ------------ |
| `zhihu`         | 知乎           |
| `weibo`         | 微博           |
| `zaobao`        | 联合早报         |
| `coolapk`       | 酷安           |
| `douyin`        | 抖音           |
| `hupu`          | 虎扑           |
| `tieba`         | 百度贴吧         |
| `toutiao`       | 今日头条         |
| `ithome`        | IT之家         |
| `thepaper`      | 澎湃新闻         |
| `sputniknewscn` | 卫星通讯社        |
| `cankaoxiaoxi`  | 参考消息         |
| `gelonghui`     | 格隆汇          |
| `solidot`       | Solidot      |
| `hackernews`    | Hacker News  |
| `producthunt`   | Product Hunt |
| `kaopu`         | 靠谱新闻         |
| `jin10`         | 金十数据         |
| `baidu`         | 百度热搜         |
| `nowcoder`      | 牛客           |
| `sspai`         | 少数派          |
| `juejin`        | 稀土掘金         |
| `ifeng`         | 凤凰网          |
| `douban`        | 豆瓣           |
| `steam`         | Steam        |
| `freebuf`       | Freebuf      |

#### 请求示例

```bash
curl "/api/s?id=zhihu"
curl "/api/s?id=hackernews"
curl "/api/s?id=freebuf"
```

---

### 3.3 带子源的父级 ID

这些父级 ID 可以请求，但通常会重定向到默认子源：

| 父级 ID          | 名称       | 默认子源                    |
| -------------- | -------- | ----------------------- |
| `v2ex`         | V2EX     | `v2ex-share`            |
| `mktnews`      | MKTNews  | `mktnews-flash`         |
| `wallstreetcn` | 华尔街见闻    | `wallstreetcn-quick`    |
| `36kr`         | 36氪      | `36kr-quick`            |
| `pcbeta`       | 远景论坛     | `pcbeta-windows11`      |
| `cls`          | 财联社      | `cls-telegraph`         |
| `xueqiu`       | 雪球       | `xueqiu-hotstock`       |
| `fastbull`     | 法布财经     | `fastbull-express`      |
| `github`       | Github   | `github-trending-today` |
| `bilibili`     | 哔哩哔哩     | `bilibili-hot-search`   |
| `linuxdo`      | LINUX DO | `linuxdo-latest`        |
| `chongbuluo`   | 虫部落      | `chongbuluo-latest`     |
| `tencent`      | 腾讯新闻     | `tencent-hot`           |
| `qqvideo`      | 腾讯视频     | `qqvideo-tv-hotsearch`  |
| `iqiyi`        | 爱奇艺      | `iqiyi-hot-ranklist`    |

#### 请求示例

```bash
curl "/api/s?id=v2ex"
curl "/api/s?id=wallstreetcn"
```

更推荐：

```bash
curl "/api/s?id=v2ex-share"
curl "/api/s?id=wallstreetcn-quick"
```

---

### 3.4 具体子源 ID 列表

#### V2EX

* `v2ex-share`

#### MKTNews

* `mktnews-flash`

#### 华尔街见闻

* `wallstreetcn-quick`
* `wallstreetcn-news`
* `wallstreetcn-hot`

#### 36氪

* `36kr-quick`
* `36kr-renqi`

#### 远景论坛

* `pcbeta-windows11`

> `pcbeta-windows` 在源码中标记为 `disable: true`，不会出现在最终可用列表中。

#### 财联社

* `cls-telegraph`
* `cls-depth`
* `cls-hot`

#### 雪球

* `xueqiu-hotstock`

#### 法布财经

* `fastbull-express`
* `fastbull-news`

#### Github

* `github-trending-today`

#### 哔哩哔哩

* `bilibili-hot-search`
* `bilibili-hot-video`
* `bilibili-ranking`

> 其中 `bilibili-hot-video`、`bilibili-ranking` 在源码中标记了 `disable: "cf"`，在 Cloudflare Pages 环境下可能不会出现在最终可用列表中。

#### LINUX DO

* `linuxdo-latest`
* `linuxdo-hot`

> `linuxdo` 顶级源在源码中标记为 `disable: true`，默认不会出现在最终可用列表中。

#### 虫部落

* `chongbuluo-latest`
* `chongbuluo-hot`

#### 腾讯新闻

* `tencent-hot`

#### 腾讯视频

* `qqvideo-tv-hotsearch`

#### 爱奇艺

* `iqiyi-hot-ranklist`

---

## 4. 批量获取多个新闻源缓存

### `POST /api/s/entire`

批量读取多个新闻源的缓存结果。
注意：该接口主要用于**批量读缓存**，不是逐个强制拉取最新数据。

#### 请求体

```json
{
  "sources": ["zhihu", "weibo", "hackernews"]
}
```

#### 请求示例

```bash
curl -X POST /api/s/entire \
  -H "Content-Type: application/json" \
  -d '{"sources":["zhihu","weibo","hackernews"]}'
```

#### 响应示例

```json
[
  {
    "status": "cache",
    "id": "zhihu",
    "items": [],
    "updatedTime": 1712345678901
  },
  {
    "status": "cache",
    "id": "weibo",
    "items": [],
    "updatedTime": 1712345678901
  }
]
```

#### 说明

* 请求体字段名固定为 `sources`
* 只会处理合法的源 ID
* 返回数组
* 每个元素结构与 `/api/s` 类似，但这里主要是缓存结果，`status` 通常为 `cache`


#### 工具参数

| 参数      | 类型     | 必填 | 说明         |
| ------- | ------ | -- | ---------- |
| `id`    | string | 是  | 新闻源 ID     |
| `count` | number | 否  | 返回条数，默认 10 |

#### 工具作用

内部会调用 `/api/s?id=<id>` 获取新闻，再裁剪为指定条数后输出。

---

## 常见状态与错误

### 500 Internal Server Error

常见于：

* 源 ID 非法
* 数据结构异常
* 抓取过程异常
* 缓存过程异常
