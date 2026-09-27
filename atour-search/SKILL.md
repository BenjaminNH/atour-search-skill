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

## 怎么跟用户说

默认按普通旅客来写。价格、有没有房、开业时间和位置用日常说法。还不了解用户时，回复里不用接口、状态码、字段名或「限流」这类词。

已经能看出用户有相关专业背景时，同一件事可以说得具体一点，例如说明是连续查看房型后暂时不能继续。结论仍然先说清楚。

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

标准输出是 JSON。`ok` 为 false 时，这次查询没有成功。按「怎么跟用户说」说明原因，不要把失败说成没房。

先用 `search` 拿到酒店列表。列表里已有展示价、位置、到店说明、开业时间和酒店这一级是否有房，用来做精细筛选。按用户的价格、位置、开业时间等条件，从中选出 5 到 7 家，再对这几家的 `chain_id` 调用 `rooms`，把房型价格交给用户选。房型不在列表里。早餐和取消规则不参与筛选，也不向用户展开。

查看房型时如果因为看的店太多，后面的 `rooms` 失败，而且响应是网关拒绝（例如 HTTP 405），不要把这些店说成没房。已经查到的房型照常说明。默认向用户说明：「由于查看的详情太多，目前触发了限制，可能需要等一段时间才能继续获取详细信息。」这一轮不要再对更多店调用 `rooms`。

## 怎么读结果

字段表见 [references/results.md](references/results.md)。读的时候按这些判断：

- `--max-price` 比较 `display_price`，小于等于上限才留下。没有展示价的店不出现。`--brand` 和 `--exclude-brand` 都可以写多个品牌，跟在参数后面，或把参数重复写几次。只看时，命中其中任何一个就留下；排除时，命中其中任何一个就去掉。六个正式品牌名按相等匹配，「亚朵」和「亚朵S」要分别写。
- `--available-only` 时，列表有房的店不再查房型。列表满房的店才查房型，房型也没有可售房才去掉。房型请求失败的店会留下，`availability_from` 为 `rooms_error`，`rooms_error_status` 写明失败种类。向用户说明这次没确认成，不要说成已满房。
- `rooms` 的 `rooms_status` 为 `empty` 时，请求成功但没有房型。`blocked` 和 `rate_limited` 用上面那句「查看的详情太多」。`http_error`、`network_error` 和 `error` 是没查成，退出码是 1，`ok` 为 false。这些都不要说成没房。
- 房型结果保留每一间，包括已满的。`bookable` 为 false 时，`display_price` 只是满房时看到的价格，不能当成还能订的价格。`room_summary.lowest_returned` 是这次返回里最低的一间，它已满时说明名称和已满；`lowest_sellable` 是当前还能订的最低一间。两间都要说。用户问的是另一种床型时，只要这间低价房会让酒店起价被理解错，也要说。
- 用户点名床型时，在房型名称里查找。找到的都已满，说该类房型当前无可售房。没有这个名称，说这次没有返回该房型，不要说它已满。
- 列表里的 `display_price` 和 `available` 是酒店这一级。`--max-price` 比的是酒店起价。用户指定了房型、而这间的价格还没查到时，不能说它满足价格条件，也不能因为酒店显示有房就说这间有房。
- 给用户说明时，先说日期、条件和有多少家已经能确认、有多少家还没确认。再按需要列出店名、位置、开业时间、可订房型和价格。低价房已满、价格还不是指定房型、暂时没查到，单独写出来。店多时说明还有多少家，不要把没展开的说成不符合条件。电话和长地址等用户问了再补。这是组织方式，不是固定模板。
- 搜索里个别开业时间失败时，整次查询仍然成功。用每家的 `open_date_status` 区分：`missing` 是没有返回日期，`error` 是详情请求失败。
- 地铁和到店路线先读响应里的 `access_hint`，再读 `address` 和 `access_note`。两处都是原文。程序不挑选站点或步行距离。原文没写地铁，只表示没提到。
- `queried_at` 是这份 JSON 组装出来的时间。`display_price` 是当时的未登录展示价。

## 价格和开业时间

先读响应里的 `price_note`。

不需要配置 token。`display_price` 是未登录状态下亚朵 App 的展示价。常见 `price_plan` 是「注册会员立付立减价」或「开业特惠」，也会出现其他方案，例如「提前3天预订优惠」。会与登录后的会员价有一定差距。`market_price` 是门市价。

`open_date` 来自每家酒店的详情。常见写法是「2024年8月开业」，精确到月。用它判断店有多新。`price_plan` 里的「开业特惠」只是价格方案的名字。
