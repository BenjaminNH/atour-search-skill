# 查询结果

命令只把 JSON 打到标准输出。字段名以这里为准。

## 三个命令

| 命令 | 作用 | 请求 |
| --- | --- | --- |
| `cities` | 已开业城市，可用 `--province` 缩小 | 城市列表，一次 |
| `search` | 一个城市加入住、离店日期 | 列表分页，然后每家留下的店一次详情 |
| `rooms` | 一个 `chain_id` 的房型 | 房型报价，一次 |

`search` 一次只查一个城市。城市酒店少就快；酒店多就要为每家店补开业时间，会慢。

## search 的筛选顺序

1. 拉取该城市的酒店列表。
2. 按 `--brand` 筛选。传入「亚朵」「亚朵S」「亚朵X」「亚朵轻居」「亚朵见野」「亚朵V3.6」时按品牌相等匹配；其他文字按品牌或店名包含匹配。
3. 若给了 `--near-lat` 和 `--near-lng`，用国测局坐标计算直线距离。`--radius-km` 在这一步丢掉圈外的店。
4. 为留下的每家店请求开业时间和电话。
5. 排序。未指定时，有坐标按 `distance`，否则按 `price`。
6. `--limit` 截断条数。

`--sort` 可以是 `price`（有房且展示价低的在前）、`open_date`（较新的在前）、`distance`（更近的在前）、`score`（评分高的在前）。

## 酒店字段

| 字段 | 含义 |
| --- | --- |
| `chain_id` | 酒店编号，查房型时使用 |
| `name` | 店名 |
| `brand` | 从店名推断：亚朵、亚朵S、亚朵X、亚朵轻居、亚朵见野、亚朵V3.6 |
| `address` | 地址 |
| `area` | 城市 / 区域 |
| `business_area` | 商圈 |
| `latitude`、`longitude` | 国测局坐标 GCJ-02 |
| `distance_to_center_km` | 接口给出的距市中心公里数 |
| `distance_text` | 接口的距离说明，例如「距市中心直线1.3公里」 |
| `distance_km` | 只在提供了周边坐标时出现，表示到该坐标的直线距离 |
| `display_price` | 未登录时的 App 展示价。和登录后的金卡或铂金个人价会有细微差别。不需要配置 token |
| `market_price` | 门市价 |
| `price_plan` | 价格方案名称 |
| `available` | 是否有房 |
| `score` | 评分 |
| `review_count` | 点评数 |
| `cover_url` | 封面图 |
| `open_date` | 开业时间原文。空字符串表示这次详情没有返回日期 |
| `phone` | 详情里的电话。列表里通常没有，所以放在同一次开业时间请求中读取。空字符串表示没有 |

响应顶层还有 `count`、`open_date_missing`、`price_note` 和 `query`。`open_date_missing` 是本页结果里没有开业时间的条数。

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

房型展示价和列表展示价来自同一类 App 价格。读法与该响应里的 `price_note` 相同。`rooms` 为空时，报价接口没有返回房型；网络失败时上游查询函数也会得到空列表。

## 退出码

| 码 | 含义 |
| --- | --- |
| 0 | `ok` 为 true |
| 1 | 接口失败 |
| 2 | 参数不正确，例如日期颠倒、坐标只给了一个、省份名不存在 |
