# 查询结果

命令只把 JSON 打到标准输出。字段名以这里为准。

## 三个命令

| 命令 | 作用 | 请求 |
| --- | --- | --- |
| `cities` | 已开业城市，可用 `--province` 缩小 | 城市列表，一次 |
| `search` | 一个城市加入住、离店日期 | 列表分页，然后每家留下的店一次详情 |
| `rooms` | 一个 `chain_id` 的房型 | 房型报价，一次 |

`search` 一次只查一个城市。城市酒店少就快；酒店多就要为每家店补开业时间，会慢。使用 `--available-only` 时，列表已标满房的店会先查一次房型。

## search 的筛选顺序

1. 拉取该城市的酒店列表。
2. 按 `--brand` 保留。可以一次写多个，例如 `--brand 亚朵 亚朵S`，也可以重复写 `--brand`。命中其中任何一个就留下。传入「亚朵」「亚朵S」「亚朵X」「亚朵轻居」「亚朵见野」「亚朵V3.6」时按品牌相等匹配，「亚朵」不会包含「亚朵S」。其他文字按品牌或店名包含匹配。
3. 按 `--exclude-brand` 排除。写法和匹配规则与 `--brand` 相同。命中其中任何一个就去掉，「亚朵」和「亚朵S」要分别写。
4. `--max-price` 按展示价比较，`display_price` `<=` 上限才留下。没有展示价的店丢掉。
5. 若给了 `--near-lat` 和 `--near-lng`，用国测局坐标计算直线距离。`--radius-km` 在这一步丢掉圈外的店。
6. `--available-only`。列表标为有房的店保留，不请求房型。列表标为满房的店请求一次房型。只有该请求成功，且没有可售房（没有房型，或每间都满房），才去掉这家店。房型请求失败则保留。
7. 为留下的每家店请求开业时间和电话。
8. 排序。未指定时，有坐标按 `distance`，否则按 `price`。
9. `--limit` 截断条数。

`--sort` 可以是 `price`（有房且展示价低的在前）、`open_date`（较新的在前）、`distance`（更近的在前）、`score`（评分高的在前）。

## 酒店字段

| 字段 | 含义 |
| --- | --- |
| `chain_id` | 酒店编号，查房型时使用 |
| `name` | 店名 |
| `brand` | 从店名推断：亚朵、亚朵S、亚朵X、亚朵轻居、亚朵见野、亚朵V3.6 |
| `address` | 地址 |
| `access_note` | 列表字段 mapRemark 的原文，可能为空，不解析 |
| `area` | 城市 / 区域 |
| `business_area` | 商圈 |
| `latitude`、`longitude` | 国测局坐标 GCJ-02 |
| `distance_to_center_km` | 接口给出的距市中心公里数 |
| `distance_text` | 接口的距离说明，例如「距市中心直线1.3公里」 |
| `distance_km` | 只在提供了周边坐标时出现，表示到该坐标的直线距离 |
| `display_price` | 未登录时的 App 展示价，会与登录后的会员价有一定差距。不需要配置 token |
| `market_price` | 门市价 |
| `price_plan` | 价格方案名称 |
| `available` | 是否有房 |
| `availability_from` | `list`、`rooms` 或 `rooms_error` |
| `rooms_error` | 空字符串。只有为确认有房而请求房型失败时才有内容 |
| `rooms_error_status` | 空字符串，或 `error`、`blocked`、`rate_limited`、`http_error`、`network_error`。有内容时表示这次没确认成，不是没房 |
| `score` | 评分 |
| `review_count` | 点评数 |
| `cover_url` | 封面图 |
| `open_date` | 开业时间原文。空字符串表示这次详情没有给出日期 |
| `open_date_status` | `ok`、`missing` 或 `error`。用来区分没有日期和请求失败 |
| `open_date_error` | 空字符串。只有出错时才有内容 |
| `phone` | 详情里的电话。列表里通常没有，所以放在同一次开业时间请求中读取。空字符串表示没有 |

`open_date` 为空表示详情没有给出日期。`open_date_status` 区分没有日期和请求失败。

响应顶层还有 `count`、`open_date_missing`、`open_date_errors`、`queried_at`、`price_source`、`access_hint`、`price_note` 和 `query`。`open_date_missing` 统计本页 `open_date` 为空的条数。`open_date_errors` 统计 `open_date_status` 为 `error` 的条数。列表成功的 search，即使部分详情失败，退出码仍是 0。

`queried_at` 是组装这份 JSON 时的本地时间，带时区偏移，不是锁定价格的时间。`price_source` 为 `logged_out_app_display`。`access_hint` 固定为：地铁和到店路线可能写在 address 或 access_note，两处都要读。原文没写地铁只表示没提到。distance_text 是距市中心的直线距离。程序不挑选站点和距离。

`query` 还会回显 `brand`、`exclude_brand`、`max_price` 和 `available_only`。`brand` 和 `exclude_brand` 是品牌名列表，没有筛选时为空列表。

## 房型字段

| 字段 | 含义 |
| --- | --- |
| `name` | 房型名 |
| `display_price` | 该房型的 App 展示价 |
| `market_price` | 门市价 |
| `breakfast` | 早餐份数 |
| `cancel_policy` | 取消规则 |
| `min_nights` | 最少入住晚数 |
| `sold_out` | 是否满房 |
| `bookable` | 还能订时为 true。为 false 时，`display_price` 是满房展示价，不是当前可订价 |

`rooms_status` 为 `ok` 时还有 `room_summary`：`sellable_count`、`sold_out_count`、`all_sold_out`、`lowest_returned`、`lowest_sellable`。后两项是 `{name, display_price, sold_out, bookable}`，没有对应房型时为 null。`lowest_returned` 是返回结果里的最低价，满房也保留。`lowest_sellable` 是当前可订的最低价。

房型展示价和列表展示价来自同一类 App 价格。读法与该响应里的 `price_note` 相同。`rooms_status` 为 `ok`、`empty`、`error`、`blocked`、`rate_limited`、`http_error` 或 `network_error`。`empty` 是请求成功但没有房型，退出码为 0。其余失败状态退出码为 1，`ok` 为 false，`rooms` 为 []，不能当成没房。`blocked` 表示短时间查看的房型详情太多，同一轮后续报价不再发请求。`rate_limited` 和服务器错误、超时最多再试 2 次，间隔 1.5 秒、3 秒。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | `ok` 为 true |
| 1 | 接口失败 |
| 2 | 参数不正确，例如日期颠倒、坐标只给了一个、省份名不存在、`--max-price` 为负数 |
