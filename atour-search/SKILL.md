---
name: atour-search
description: >
  查询亚朵已开业酒店的展示价、价格方案、开业时间和房型。
  在规划行程、比较亚朵门店、按城市和入住日期询价、按展示价或品牌筛选、确认是否有房、开业时间或房型价格时使用。
  不下单，不查询其他酒店集团。
license: MIT. See LICENSE.
compatibility: 需要 Python 3.10+、requests，以及访问 yaduo.com 的网络。不需要配置 token。
---

# 亚朵查询

这个 Skill 没有模型，也不能下单。需要亚朵门店、价格或开业时间时，运行脚本，阅读标准输出的 JSON。

## 什么时候查

用户要按城市和入住日期比较亚朵酒店、看展示价、确认开业时间或房型时使用。

一次查一个城市。城市越小、酒店越少，越快。范围大、酒店多时，每家店都要再请求一次开业时间，查询会变慢。`--brand`、`--exclude-brand`、`--max-price`、`--radius-km` 和 `--available-only` 会先缩小名单，再为留下的店查开业时间。`--limit` 只缩短输出，不会少查开业时间。

不要连续查很多城市，也不要把查询改成按省批量扫描。

不用于下单、支付，也不用于其他酒店集团。

## 怎么调用

依赖：

```bash
pip install -r scripts/requirements.txt
```

在本 Skill 目录执行：

```bash
python scripts/atour_search.py cities --province 浙江
python scripts/atour_search.py search --city 杭州 --check-in 2026-10-01 --check-out 2026-10-02
python scripts/atour_search.py search --city 杭州 --check-in 2026-10-01 --check-out 2026-10-02 --brand 轻居 --near-lat 30.2428 --near-lng 120.1485 --radius-km 5
python scripts/atour_search.py search --city 长沙 --check-in 2026-09-28 --check-out 2026-09-29 --brand 亚朵 亚朵S --max-price 400 --available-only
python scripts/atour_search.py search --city 长沙 --check-in 2026-09-28 --check-out 2026-09-29 --exclude-brand 亚朵轻居 亚朵见野
python scripts/atour_search.py rooms --chain-id 3301155 --check-in 2026-10-01 --check-out 2026-10-02
```

日期是 `YYYY-MM-DD`，离店必须晚于入住。`--near-lat` 和 `--near-lng` 用国测局坐标 GCJ-02，和接口一致。不需要配置 token。

标准输出是 JSON。`ok` 为 false 时，向用户说明 `error`，不要把这次调用当成查询成功。

先用 `search` 选店，再对入围的 `chain_id` 调用 `rooms`。房型不在列表里。

## 怎么读结果

字段表见 [references/results.md](references/results.md)。读的时候按这些判断：

- `--max-price` 比较 `display_price`，小于等于上限才留下。没有展示价的店不出现。`--brand` 和 `--exclude-brand` 都可以写多个品牌，跟在参数后面，或把参数重复写几次。只看时，命中其中任何一个就留下；排除时，命中其中任何一个就去掉。六个正式品牌名按相等匹配，「亚朵」和「亚朵S」要分别写。
- `--available-only` 时，列表有房的店不再查房型。列表满房的店才查房型，房型也没有可售房才去掉。房型请求失败的店会留下，`availability_from` 为 `rooms_error`，向用户说明这次没确认成，不要说成已满房。
- `rooms` 的 `rooms_status` 为 `empty` 时，请求成功但没有房型。为 `error` 时请求失败，退出码是 1，`ok` 为 false，向用户说明 `error`。
- 搜索里个别开业时间失败时，整次查询仍然成功。用每家的 `open_date_status` 区分：`missing` 是没有返回日期，`error` 是详情请求失败。
- 地铁和到店路线先读响应里的 `access_hint`，再读 `address` 和 `access_note`。两处都是原文。程序不挑选站点或步行距离。原文没写地铁，只表示没提到。
- `queried_at` 是这份 JSON 组装出来的时间。`display_price` 是当时的未登录展示价。

## 价格和开业时间

先读响应里的 `price_note`。

不需要配置 token。`display_price` 是未登录状态下亚朵 App 的展示价。常见 `price_plan` 是「注册会员立付立减价」或「开业特惠」，也会出现其他方案，例如「提前3天预订优惠」。会与登录后的会员价有一定差距。`market_price` 是门市价。

`open_date` 来自每家酒店的详情。常见写法是「2024年8月开业」，精确到月。用它判断店有多新。`price_plan` 里的「开业特惠」只是价格方案的名字。
