import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "atour-search" / "scripts"))

import atour_api


def _clear_caches() -> None:
    atour_api._CHAIN_BASE_CACHE.clear()
    atour_api._OPEN_DATE_CACHE.clear()
    atour_api._PHONE_CACHE.clear()
    atour_api._ROOM_CACHE.clear()


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class ChainBaseTests(unittest.TestCase):
    def setUp(self):
        _clear_caches()
        self.delay = patch.object(atour_api, "_request_delay_light").start()
        self.post = patch.object(atour_api.requests, "post").start()
        self.addCleanup(patch.stopall)

    def test_ok_caches_and_skips_the_next_request(self):
        self.post.return_value = _Response({
            "success": True,
            "result": {"chainBase": {"openDate": "2024年8月开业", "phoneNum": "0731-1"}},
        })
        first = atour_api.fetch_chain_base(11)
        second = atour_api.fetch_chain_base(11)
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["open_date"], "2024年8月开业")
        self.assertEqual(first["phone"], "0731-1")
        self.assertEqual(second, first)
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(self.delay.call_count, 1)
        self.assertEqual(atour_api._fetch_open_date(11, ""), "2024年8月开业")
        self.assertEqual(self.post.call_count, 1)

    def test_missing_date_is_distinct_from_request_failure(self):
        self.post.return_value = _Response({
            "success": True,
            "result": {"chainBase": {"openDate": "  ", "phoneNum": "0731-2"}},
        })
        missing = atour_api.fetch_chain_base(12)
        self.assertEqual(missing["status"], "missing")
        self.assertEqual(missing["open_date"], "")
        self.assertEqual(missing["phone"], "0731-2")
        self.assertEqual(atour_api._OPEN_DATE_CACHE["12"], "—")

        self.post.side_effect = atour_api.requests.RequestException("down")
        failed = atour_api.fetch_chain_base(13)
        self.assertEqual(failed["status"], "error")
        self.assertIn("开业时间接口请求失败", failed["error"])
        self.assertNotIn("13", atour_api._CHAIN_BASE_CACHE)
        self.assertNotIn("13", atour_api._OPEN_DATE_CACHE)

        self.post.side_effect = None
        self.post.return_value = _Response({
            "success": True,
            "result": {"chainBase": {"openDate": "2020年1月开业", "phoneNum": ""}},
        })
        retried = atour_api.fetch_chain_base(13)
        self.assertEqual(retried["status"], "ok")
        self.assertEqual(self.post.call_count, 3)

    def test_api_failure_is_not_cached(self):
        self.post.return_value = _Response({"success": False, "code": 9, "msg": "limited"})
        failed = atour_api.fetch_chain_base(14)
        self.assertEqual(failed["status"], "error")
        self.assertIn("code=9", failed["error"])
        self.assertNotIn("14", atour_api._CHAIN_BASE_CACHE)


class RoomsResultTests(unittest.TestCase):
    def setUp(self):
        _clear_caches()
        patch.object(atour_api, "_request_delay_light").start()
        self.post = patch.object(atour_api.requests, "post").start()
        self.addCleanup(patch.stopall)

    def test_empty_success_is_cached_and_error_is_not(self):
        self.post.return_value = _Response({
            "success": True,
            "result": {"priceResponse": {"chainRoomList": []}},
        })
        stay = date(2026, 9, 28), date(2026, 9, 29)
        empty = atour_api.fetch_rooms_result(21, *stay)
        self.assertEqual(empty["status"], "empty")
        self.assertEqual(empty["rooms"], [])
        atour_api.fetch_rooms_result(21, *stay)
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(atour_api.get_hotel_rooms(21, *stay), [])

        self.post.side_effect = atour_api.requests.ConnectionError("reset")
        failed = atour_api.fetch_rooms_result(22, *stay)
        self.assertEqual(failed["status"], "error")
        self.assertEqual(atour_api.get_hotel_rooms(22, *stay), [])
        self.assertNotIn(("22", str(stay[0]), str(stay[1])), atour_api._ROOM_CACHE)
        self.post.side_effect = None
        self.post.return_value = _Response({
            "success": None,
            "result": {"priceResponse": {"chainRoomList": [{
                "roomTypeInfoResponse": {"roomTypeName": "大床"},
                "minRoomPrice": {"showPrice": 356, "marketPrice": 500, "isFullRoom": False},
            }]}},
        })
        ok = atour_api.fetch_rooms_result(22, *stay)
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["rooms"][0]["房型"], "大床")
        self.assertEqual(ok["rooms"][0]["是否满房"], "有房")
        self.assertEqual(ok["rooms"][0]["铂金会员价"], 356.0)

    def test_sold_out_room_stays_in_an_ok_result(self):
        self.post.return_value = _Response({
            "result": {"priceResponse": {"chainRoomList": [{
                "roomTypeInfoResponse": {"roomTypeName": "双床"},
                "minRoomPrice": {"showPrice": 300, "isFullRoom": True},
            }]}},
        })
        result = atour_api.fetch_rooms_result(23, date(2026, 9, 28), date(2026, 9, 29))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rooms"][0]["是否满房"], "满房")


class NormalizeTests(unittest.TestCase):
    def test_map_remark_is_copied_unchanged(self):
        row = atour_api._normalize_hotel({
            "name": "长沙滨江金融中心亚朵酒店",
            "showPrice": 356,
            "fullRoom": False,
            "address": "银双路49号",
            "mapRemark": "地铁4号线六沟垅站5号口出\n步行10米",
            "distanceInfo": "距市中心直线4公里",
        })
        self.assertEqual(row["到店说明"], "地铁4号线六沟垅站5号口出\n步行10米")
        self.assertEqual(row["地址"], "银双路49号")
        self.assertEqual(row["铂金会员价"], 356.0)


if __name__ == "__main__":
    unittest.main()
