---
name: atour-search
description: >
  查询亚朵已开业酒店的展示价、价格方案、开业时间和房型。
  在规划行程、比较亚朵门店、按城市和入住日期询价、确认开业时间或房型价格时使用。
  不下单，不查询其他酒店集团。
license: MIT. See LICENSE.
compatibility: 需要 Python 3.10+、requests，以及访问 yaduo.com 的网络。不需要配置 token。
---

# 亚朵查询

这个 Skill 没有模型，也不能下单。需要亚朵门店、价格或开业时间时，运行脚本，阅读标准输出的 JSON。

## 什么时候查

用户要按城市和入住日期比较亚朵酒店、看展示价、确认开业时间或房型时使用。

一次查一个城市。城市越小、酒店越少，越快。范围大、酒店多时，每家店都要再请求一次开业时间，查询会变慢。`--brand` 和 `--radius-km` 会先缩小名单，再为留下的店查开业时间。`--limit` 只缩短输出，不会少查开业时间。

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
python scripts/atour_search.py rooms --chain-id 3301155 --check-in 2026-10-01 --check-out 2026-10-02
```

日期是 `YYYY-MM-DD`，离店必须晚于入住。`--near-lat` 和 `--near-lng` 用国测局坐标 GCJ-02，和接口一致。不需要配置 token。

标准输出是 JSON。`ok` 为 false 时，向用户说明 `error`，不要把这次调用当成查询成功。

先用 `search` 选店，再对入围的 `chain_id` 调用 `rooms`。房型不在列表里。

## 价格和开业时间

先读响应里的 `price_note`。

不需要配置 token。`display_price` 是未登录状态下亚朵 App 的展示价。常见 `price_plan` 是「注册会员立付立减价」或「开业特惠」，也会出现其他方案，例如「提前3天预订优惠」。它和登录后的金卡或铂金个人价会有细微差别。`market_price` 是门市价。

`open_date` 来自每家酒店的详情。常见写法是「2024年8月开业」，精确到月。用它判断店有多新。`price_plan` 里的「开业特惠」只是价格方案的名字。

字段表见 [references/results.md](references/results.md)。
