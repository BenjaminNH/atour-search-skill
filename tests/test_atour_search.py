"""Stdlib tests for atour_search. They never call the network."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "atour-search" / "scripts"))

import atour_api  # noqa: E402

# The query module may not export this name until its parallel update lands.
# Stub it in memory so the CLI can import; each test still patches atour_search.
if not hasattr(atour_api, "fetch_rooms_result"):

    def _stub_fetch_rooms_result(chain_id, start_date, end_date):
        return {"status": "error", "rooms": [], "error": "not implemented"}

    atour_api.fetch_rooms_result = _stub_fetch_rooms_result

import atour_search  # noqa: E402


ACCESS_HINT = (
    "地铁和到店路线可能写在 address 或 access_note，两处都要读。"
    "原文没写地铁只表示没提到。"
    "distance_text 是距市中心的直线距离。程序不挑选站点和距离。"
)


def hotel(**overrides):
    row = {
        "酒店名称": "测试酒店",
        "酒店类型": "亚朵",
        "开业时间": "",
        "地址": "杭州市西湖区某路1号",
        "位置": "西湖",
        "地段/商圈": "湖滨",
        "距离说明": "距市中心约1公里",
        "价格方案": "注册会员立付立减价",
        "铂金会员价": 300,
        "是否有房": "有房",
        "latitude": 30.25,
        "longitude": 120.15,
        "chainId": 1001,
        "封面图": "",
        "评分": 4.8,
        "点评数": 12,
        "距市公里": 1.2,
        "门市价": 500,
        "到店说明": "",
        "电话": "0571-00000000",
    }
    row.update(overrides)
    return row


def search_argv(*extra: str) -> list[str]:
    return [
        "search",
        "--city",
        "杭州",
        "--check-in",
        "2026-10-01",
        "--check-out",
        "2026-10-02",
        *extra,
    ]


def rooms_argv() -> list[str]:
    return [
        "rooms",
        "--chain-id",
        "3301155",
        "--check-in",
        "2026-10-01",
        "--check-out",
        "2026-10-02",
    ]


def invoke(argv, *, rows=None, fetch_fn=None, rooms_fn=None, enrich_fn=None):
    calls = {"fetch": [], "rooms": [], "enrich": []}

    def fetch(*args, **kwargs):
        calls["fetch"].append((args, kwargs))
        if fetch_fn is not None:
            return fetch_fn(*args, **kwargs)
        return list(rows or [])

    def rooms(*args, **kwargs):
        calls["rooms"].append(args)
        if rooms_fn is not None:
            return rooms_fn(*args, **kwargs)
        return {"status": "error", "rooms": [], "error": "unexpected"}

    def enrich(passed, *args, **kwargs):
        calls["enrich"].append([row.get("chainId") for row in passed])
        if enrich_fn is not None:
            return enrich_fn(passed, *args, **kwargs)
        for row in passed:
            if "开业状态" in row:
                continue
            if row.get("开业时间") in (None, "", "—"):
                row["开业时间"] = "2024年8月开业"

    buf = io.StringIO()
    with (
        patch.object(atour_search, "fetch_atour_prices", fetch),
        patch.object(atour_search, "enrich_open_dates", enrich),
        patch.object(atour_search, "fetch_rooms_result", rooms),
        redirect_stdout(buf),
    ):
        code = atour_search.main(list(argv))
    return code, json.loads(buf.getvalue()), calls


class AtourSearchTests(unittest.TestCase):
    def test_max_price_drops_null_and_above_cap_before_open_dates(self):
        rows = [
            hotel(chainId=1, 酒店名称="无价", 铂金会员价=None),
            hotel(chainId=2, 酒店名称="超价", 铂金会员价=250),
            hotel(chainId=3, 酒店名称="封顶", 铂金会员价=200),
            hotel(chainId=4, 酒店名称="更低", 铂金会员价=150),
        ]
        code, payload, calls = invoke(search_argv("--max-price", "200"), rows=rows)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(item["chain_id"] for item in payload["hotels"]), [3, 4])
        self.assertEqual(payload["query"]["max_price"], 200)
        enriched = [chain_id for batch in calls["enrich"] for chain_id in batch]
        self.assertEqual(sorted(enriched), [3, 4])
        self.assertNotIn(1, enriched)
        self.assertNotIn(2, enriched)

    def test_negative_max_price_exits_2_without_fetch(self):
        code, payload, calls = invoke(search_argv("--max-price", "-1"), rows=[hotel()])
        self.assertEqual(code, 2)
        self.assertEqual(payload, {"ok": False, "error": "max-price 需要是非负数"})
        self.assertEqual(calls["fetch"], [])
        self.assertEqual(calls["rooms"], [])
        self.assertEqual(calls["enrich"], [])

    def test_exclude_brand_drops_only_exact_brand(self):
        rows = [
            hotel(chainId=1, 酒店名称="杭州亚朵轻居", 酒店类型="亚朵轻居"),
            hotel(chainId=2, 酒店名称="杭州亚朵", 酒店类型="亚朵"),
            hotel(chainId=3, 酒店名称="杭州亚朵S", 酒店类型="亚朵S"),
            hotel(chainId=4, 酒店名称="名字里有亚朵轻居", 酒店类型="亚朵"),
        ]
        code, payload, calls = invoke(search_argv("--exclude-brand", "亚朵轻居"), rows=rows)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(item["chain_id"] for item in payload["hotels"]), [2, 3, 4])
        self.assertEqual(sorted(item["brand"] for item in payload["hotels"]), ["亚朵", "亚朵", "亚朵S"])
        self.assertEqual(payload["query"]["exclude_brand"], ["亚朵轻居"])
        enriched = [chain_id for batch in calls["enrich"] for chain_id in batch]
        self.assertEqual(sorted(enriched), [2, 3, 4])

    def test_brand_filters_accept_several_names(self):
        rows = [
            hotel(chainId=1, 酒店名称="杭州亚朵轻居", 酒店类型="亚朵轻居"),
            hotel(chainId=2, 酒店名称="杭州亚朵", 酒店类型="亚朵"),
            hotel(chainId=3, 酒店名称="杭州亚朵S", 酒店类型="亚朵S"),
            hotel(chainId=4, 酒店名称="杭州亚朵X", 酒店类型="亚朵X"),
        ]
        cases = [
            (["--exclude-brand", "亚朵", "亚朵S"], [1, 4]),
            (["--exclude-brand", "亚朵", "--exclude-brand", "亚朵S"], [1, 4]),
            (["--exclude-brand=亚朵", "--exclude-brand=亚朵S"], [1, 4]),
            (["--brand", "亚朵", "亚朵S"], [2, 3]),
            (["--brand", "亚朵", "--brand", "亚朵S"], [2, 3]),
        ]
        for extra, kept in cases:
            with self.subTest(extra=extra):
                code, payload, _calls = invoke(search_argv(*extra), rows=rows)
                self.assertEqual(code, 0)
                self.assertEqual(sorted(item["chain_id"] for item in payload["hotels"]), kept)

    def test_available_only_skips_rooms_when_list_has_room(self):
        rows = [hotel(chainId=21, 是否有房="有房")]
        code, payload, calls = invoke(search_argv("--available-only"), rows=rows)
        self.assertEqual(code, 0)
        self.assertEqual(calls["rooms"], [])
        hotel_row = payload["hotels"][0]
        self.assertTrue(hotel_row["available"])
        self.assertEqual(hotel_row["availability_from"], "list")
        self.assertEqual(hotel_row["rooms_error"], "")
        self.assertEqual(calls["enrich"], [[21]])

    def test_available_only_drops_full_hotels_without_sellable_rooms(self):
        rows = [
            hotel(chainId=11, 酒店名称="空房型", 是否有房="满房"),
            hotel(chainId=12, 酒店名称="全部满房", 是否有房="满房"),
        ]

        def rooms_fn(chain_id, start, end):
            self.assertEqual(start, date(2026, 10, 1))
            self.assertEqual(end, date(2026, 10, 2))
            if chain_id == 11:
                return {"status": "empty", "rooms": [{"是否满房": "有房"}], "error": ""}
            return {
                "status": "ok",
                "rooms": [{"是否满房": "满房"}, {"是否满房": "满房"}],
                "error": "",
            }

        code, payload, calls = invoke(
            search_argv("--available-only"),
            rows=rows,
            rooms_fn=rooms_fn,
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["hotels"], [])
        self.assertEqual([item[0] for item in calls["rooms"]], [11, 12])
        self.assertEqual(calls["enrich"], [])

    def test_available_only_keeps_list_full_hotel_when_a_room_is_open(self):
        rows = [hotel(chainId=31, 是否有房="满房", 酒店名称="房型有房")]

        def rooms_fn(chain_id, start, end):
            return {
                "status": "ok",
                "rooms": [{"是否满房": "满房"}, {"是否满房": "有房"}],
                "error": "",
            }

        code, payload, calls = invoke(
            search_argv("--available-only"),
            rows=rows,
            rooms_fn=rooms_fn,
        )
        self.assertEqual(code, 0)
        hotel_row = payload["hotels"][0]
        self.assertTrue(hotel_row["available"])
        self.assertEqual(hotel_row["availability_from"], "rooms")
        self.assertEqual(hotel_row["rooms_error"], "")
        self.assertEqual(calls["enrich"], [[31]])
        self.assertEqual(len(calls["rooms"]), 1)

    def test_available_only_keeps_list_full_hotel_when_rooms_error(self):
        rows = [hotel(chainId=41, 是否有房="满房", 酒店名称="房型失败")]

        def rooms_fn(chain_id, start, end):
            return {"status": "error", "rooms": [], "error": "房型接口超时"}

        code, payload, calls = invoke(
            search_argv("--available-only"),
            rows=rows,
            rooms_fn=rooms_fn,
        )
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        hotel_row = payload["hotels"][0]
        self.assertEqual(hotel_row["availability_from"], "rooms_error")
        self.assertEqual(hotel_row["rooms_error"], "房型接口超时")
        self.assertFalse(hotel_row["available"])
        self.assertEqual(calls["enrich"], [[41]])

    def test_available_only_off_does_not_fetch_rooms(self):
        rows = [hotel(chainId=51, 是否有房="满房")]
        code, payload, calls = invoke(search_argv(), rows=rows)
        self.assertEqual(code, 0)
        self.assertEqual(calls["rooms"], [])
        self.assertEqual(payload["hotels"][0]["availability_from"], "list")
        self.assertFalse(payload["hotels"][0]["available"])
        self.assertEqual(payload["query"]["available_only"], False)
        self.assertEqual(calls["enrich"], [[51]])

    def test_open_date_error_stays_in_successful_search(self):
        def enrich(rows, *args, **kwargs):
            rows[0]["开业时间"] = "—"
            rows[0]["开业状态"] = "error"
            rows[0]["详情错误"] = "详情接口失败"

        code, payload, _calls = invoke(
            search_argv(),
            rows=[hotel(chainId=61)],
            enrich_fn=enrich,
        )
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        hotel_row = payload["hotels"][0]
        self.assertEqual(hotel_row["open_date"], "")
        self.assertEqual(hotel_row["open_date_status"], "error")
        self.assertEqual(hotel_row["open_date_error"], "详情接口失败")
        self.assertEqual(payload["open_date_errors"], 1)
        self.assertEqual(payload["open_date_missing"], 1)

    def test_access_note_comes_from_arrival_text_unchanged(self):
        note = "  地铁2号线龙翔桥站A口，南门进入  "
        code, payload, _calls = invoke(
            search_argv(),
            rows=[hotel(chainId=71, 到店说明=note, 地址="杭州市西湖区某路1号")],
        )
        self.assertEqual(code, 0)
        self.assertEqual(payload["hotels"][0]["access_note"], note)
        self.assertEqual(payload["hotels"][0]["address"], "杭州市西湖区某路1号")

    def test_search_json_includes_query_time_price_source_and_access_hint(self):
        code, payload, calls = invoke(search_argv(), rows=[hotel(chainId=81)])
        self.assertEqual(code, 0)
        self.assertEqual(payload["price_source"], "logged_out_app_display")
        self.assertEqual(payload["access_hint"], ACCESS_HINT)
        self.assertNotIn(".", payload["queried_at"])
        self.assertIsNotNone(datetime.fromisoformat(payload["queried_at"]).tzinfo)
        self.assertEqual(payload["query"]["max_price"], None)
        self.assertEqual(payload["query"]["brand"], [])
        self.assertEqual(payload["query"]["exclude_brand"], [])
        self.assertIs(payload["query"]["available_only"], False)
        self.assertIn("会与登录后的会员价有一定差距。", payload["price_note"])
        self.assertNotIn("细微差别", payload["price_note"])
        self.assertNotIn("金卡或铂金", payload["price_note"])
        self.assertEqual(payload["hotels"][0]["open_date_status"], "ok")
        self.assertEqual(payload["hotels"][0]["open_date_error"], "")
        self.assertEqual(payload["open_date_errors"], 0)
        self.assertEqual(calls["fetch"][0][1]["enrich_open_date"], False)
        self.assertEqual(calls["rooms"], [])

    def test_rooms_error_exits_1_and_empty_exits_0(self):
        def error_fn(chain_id, start, end):
            return {
                "status": "error",
                "rooms": [{"房型": "不应出现", "是否满房": "有房", "铂金会员价": 100}],
                "error": "接口失败",
            }

        code, payload, calls = invoke(rooms_argv(), rooms_fn=error_fn)
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["rooms_status"], "error")
        self.assertEqual(payload["error"], "接口失败")
        self.assertEqual(payload["rooms"], [])
        self.assertEqual(payload["price_source"], "logged_out_app_display")
        self.assertNotIn(".", payload["queried_at"])
        self.assertIsNotNone(datetime.fromisoformat(payload["queried_at"]).tzinfo)
        self.assertNotIn("access_hint", payload)
        self.assertIn("会与登录后的会员价有一定差距。", payload["price_note"])
        self.assertNotIn("细微差别", payload["price_note"])
        self.assertEqual(calls["fetch"], [])
        self.assertEqual(calls["rooms"][0][0], 3301155)

        def empty_fn(chain_id, start, end):
            return {
                "status": "empty",
                "rooms": [{"房型": "不应出现", "是否满房": "有房", "铂金会员价": 100}],
                "error": "",
            }

        code, payload, _calls = invoke(rooms_argv(), rooms_fn=empty_fn)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rooms_status"], "empty")
        self.assertEqual(payload["rooms"], [])
        self.assertEqual(payload["count"], 0)
        self.assertNotIn("error", payload)
        self.assertNotIn("access_hint", payload)
        self.assertEqual(payload["price_source"], "logged_out_app_display")

    def test_rooms_ok_uses_room_record(self):
        def ok_fn(chain_id, start, end):
            return {
                "status": "ok",
                "rooms": [
                    {
                        "房型": "高级大床房",
                        "铂金会员价": 288,
                        "门市价": 488,
                        "早餐数": 2,
                        "取消政策": "免费取消",
                        "最少入住晚数": 1,
                        "是否满房": "有房",
                    },
                    {
                        "房型": "双床房",
                        "铂金会员价": 320,
                        "门市价": 520,
                        "早餐数": 0,
                        "取消政策": "",
                        "最少入住晚数": 1,
                        "是否满房": "满房",
                    },
                ],
                "error": "",
            }

        code, payload, _calls = invoke(rooms_argv(), rooms_fn=ok_fn)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rooms_status"], "ok")
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["rooms"][0]["name"], "高级大床房")
        self.assertEqual(payload["rooms"][0]["display_price"], 288)
        self.assertFalse(payload["rooms"][0]["sold_out"])
        self.assertTrue(payload["rooms"][1]["sold_out"])
        self.assertEqual(payload["chain_id"], 3301155)
        self.assertNotIn("access_hint", payload)


if __name__ == "__main__":
    unittest.main()
