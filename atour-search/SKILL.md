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

这个 Skill 没有模型，也不能下单。需要亚朵门店、价格或开业时间时，运行脚本，阅读标准输出的 JSON。字段表在 [references/results.md](references/results.md)。

## 怎么跟用户说

默认按普通旅客来写。价格、有没有房、开业时间和位置用日常说法。还不了解用户时，不用接口、状态码、字段名或「限流」这类词。已经能看出用户有相关专业背景时，同一件事可以说得具体一点。结论先说清楚。

查询失败或房型暂时没查到，都说这次没确认成，不把失败说成没房。

查房型查得太多、后面的请求被拒绝时，已经查到的照常说明。默认说：「由于查看的详情太多，目前触发了限制，可能需要等一段时间才能继续获取详细信息。」这一轮不再查更多店。

先说用户最关心的信息，直接给出推荐和结果，再补充其余判断。表达适当简略，不必过细。

用了品牌、价格、开业时间、距离或房型条件时，说明这些条件。数得出留下多少家、还有多少家没放进来，就写上数量。数不出来时只说明用过的条件。没展开的店按这些条件说明，不改写成不符合用户的其他要求。

同一座城市里，市区和远郊、县级分开说。行政上属于这座城市、离市中心较远的店单独成组，例如长沙的浏阳。位置带上距市中心的直线距离（`distance_text` 或 `distance_to_center_km`）。

## 查什么

一次查一个城市。`--brand`、`--exclude-brand`、`--max-price`、`--radius-km` 和 `--available-only` 会先缩小名单，再为留下的店查开业时间。`--limit` 只缩短输出。不连续查很多城市，也不按省批量扫描。不用于下单、支付或其他酒店集团。

先用 `search`。列表里已有展示价、位置、到店说明、开业时间和酒店这一级是否有房。按用户的价格、位置、开业时间等条件，从中选出 5 到 7 家，再对这几家的 `chain_id` 一家一家调用 `rooms`。每次房型查询前脚本会随机等待 3 到 5 秒。房型不在列表里。早餐和取消规则不参与筛选。

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

日期是 `YYYY-MM-DD`，离店必须晚于入住。坐标是国测局 GCJ-02。不需要配置 token。`ok` 为 false 时，按「怎么跟用户说」说明原因。

## 怎么读结果

- `--max-price` 比的是酒店起价 `display_price`，小于等于上限才留下。没有展示价的店不出现。用户指定了房型、而这间的价格还没查到时，不能说它满足价格条件，也不能因为酒店 `available` 为真就说这间有房。
- `--brand` 和 `--exclude-brand` 可以一次写多个，或把参数重复写几次。命中其中任何一个就生效。六个正式品牌名按相等匹配，「亚朵」和「亚朵S」要分别写。
- `--available-only` 时，列表有房的店不再查房型。列表满房的店查过房型、仍然没有可售房，才去掉。房型请求失败的店留下。
- 房型结果保留每一间，包括已满的。`bookable` 为 false 的 `display_price` 是满房时看到的价格。`room_summary.lowest_returned` 已满时，说明它的名称和已满，并同时说明 `lowest_sellable`。即使用户问的是另一种床型，只要这间低价房会让酒店起价被理解错，也要说。
- 用户点名床型时，在房型名称里查找。找到的都已满，说该类房型当前无可售房。没有这个名称，说这次没有返回该房型。
- `rooms_status` 为 `empty` 时，请求成功但没有房型。`blocked` 和 `rate_limited` 用上面那句「查看的详情太多」。`http_error`、`network_error` 和 `error` 是没查成，退出码是 1。
- 个别开业时间失败时，整次搜索仍然成功。`open_date_status` 为 `missing` 是没有日期，`error` 是详情请求失败。
- 地铁和到店路线读 `address` 和 `access_note` 的原文。原文没写地铁，只表示没提到。
- 先读 `price_note`。`display_price` 是未登录时的 App 展示价，会与登录后的会员价有一定差距。`price_plan` 里的「开业特惠」只是价格方案的名字。`open_date` 常见写法是「2024年8月开业」，精确到月。`queried_at` 是这份结果组装出来的时间。
