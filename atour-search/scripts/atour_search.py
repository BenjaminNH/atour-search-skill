#!/usr/bin/env python3
"""给助手用的亚朵查询命令。只向标准输出打印 JSON。

查询请求由同目录的 atour_api.py 发出。
这里负责命令、筛选顺序，以及把结果写成助手阅读的字段。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from typing import Any

from atour_api import (
    AtourAPIError,
    enrich_open_dates,
    fetch_atour_prices,
    get_atour_cities,
    get_hotel_rooms,
)


_EXACT_BRANDS = {"亚朵", "亚朵S", "亚朵X", "亚朵轻居", "亚朵见野", "亚朵V3.6"}
_PROVINCE_SUFFIXES = ("壮族自治区", "回族自治区", "维吾尔自治区", "特别行政区", "自治区", "省", "市")
_PRICE_NOTE = (
    "不需要配置 token。"
    "display_price 是未登录状态下亚朵 App 的展示价，"
    "常见 price_plan 是「注册会员立付立减价」或「开业特惠」，也会出现其他方案。"
    "它和登录后的金卡或铂金个人价会有细微差别。"
    "market_price 是门市价。"
    "open_date 是酒店开业时间，常见到月份，例如「2024年8月开业」。"
    "price_plan 里的「开业特惠」不是开业时间。"
    "这里不下单。"
)
_ROOM_PRICE_NOTE = (
    "不需要配置 token。"
    "display_price 是该房型在未登录状态下的 App 展示价，读法和酒店列表相同。"
    "它和登录后的金卡或铂金个人价会有细微差别。"
    "market_price 是门市价。这里不下单。"
)


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日期格式应为 YYYY-MM-DD") from exc


def _emit(payload: dict[str, Any], code: int = 0) -> int:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


def _num(value: object) -> int | float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(number) and number.is_integer():
        return int(number)
    return round(number, 2)


def _text(value: object) -> str:
    return str(value or "").replace("\r", "").strip()


def _province_key(name: str) -> str:
    for suffix in _PROVINCE_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _keep_brand(row: dict[str, Any], brand: str) -> bool:
    if not brand:
        return True
    kind = row.get("酒店类型") or ""
    name = row.get("酒店名称") or ""
    if brand in _EXACT_BRANDS:
        return kind == brand
    return brand in kind or brand in name


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[object] = set()
    kept: list[dict[str, Any]] = []
    for row in rows:
        cid = row.get("chainId")
        key = cid if cid not in (None, "") else id(row)
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _hotel_record(row: dict[str, Any], with_distance: bool) -> dict[str, Any]:
    open_date = _text(row.get("开业时间"))
    if open_date == "—":
        open_date = ""
    record: dict[str, Any] = {
        "chain_id": row.get("chainId"),
        "name": _text(row.get("酒店名称")),
        "brand": _text(row.get("酒店类型")),
        "address": _text(row.get("地址")),
        "area": _text(row.get("位置")),
        "business_area": _text(row.get("地段/商圈")),
        "latitude": row.get("latitude"),
        "longitude": row.get("longitude"),
        "distance_to_center_km": _num(row.get("距市公里")),
        "distance_text": _text(row.get("距离说明")),
        "display_price": _num(row.get("铂金会员价")),
        "market_price": _num(row.get("门市价")),
        "price_plan": _text(row.get("价格方案")),
        "available": row.get("是否有房") != "满房",
        "score": _num(row.get("评分")),
        "review_count": _num(row.get("点评数")),
        "cover_url": row.get("封面图") or "",
        "open_date": open_date,
        "phone": _text(row.get("电话")),
    }
    if with_distance:
        record["distance_km"] = row.get("_distance_km")
    return record


def _room_record(room: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(room.get("房型")),
        "display_price": _num(room.get("铂金会员价")),
        "market_price": _num(room.get("门市价")),
        "breakfast": room.get("早餐数"),
        "cancel_policy": _text(room.get("取消政策")),
        "min_nights": room.get("最少入住晚数"),
        "sold_out": room.get("是否满房") == "满房",
    }


def _open_sort_key(hotel: dict[str, Any]) -> tuple:
    matched = re.search(r"(\d{4})年(?:(\d{1,2})月)?", hotel.get("open_date") or "")
    if not matched:
        return (1, 0, 0)
    month = int(matched.group(2) or 1)
    return (0, -int(matched.group(1)), -month)


def _sort_hotels(hotels: list[dict[str, Any]], sort: str) -> None:
    if sort == "open_date":
        hotels.sort(key=_open_sort_key)
        return
    if sort == "distance":
        hotels.sort(key=lambda item: (item.get("distance_km") is None, item.get("distance_km") or 0))
        return
    if sort == "score":
        hotels.sort(key=lambda item: (item.get("score") is None, -(item.get("score") or 0)))
        return
    hotels.sort(
        key=lambda item: (
            not item["available"],
            item["display_price"] is None,
            item["display_price"] if item["display_price"] is not None else 0,
        )
    )


def _cities(args: argparse.Namespace) -> int:
    try:
        grouped = get_atour_cities(force=True)
    except AtourAPIError as exc:
        return _emit({"ok": False, "error": str(exc)}, 1)
    if args.province:
        wanted = _province_key(args.province.strip())
        grouped = {name: cities for name, cities in grouped.items() if _province_key(name) == wanted}
        if not grouped:
            return _emit({"ok": False, "error": f"没有找到省份「{args.province.strip()}」。先运行 cities 看已开业省份。"}, 2)
    provinces = [{"name": name, "cities": cities} for name, cities in sorted(grouped.items())]
    count = sum(len(item["cities"]) for item in provinces)
    return _emit({"ok": True, "count": count, "provinces": provinces})


def _search(args: argparse.Namespace) -> int:
    near_missing = (args.near_lat is None) != (args.near_lng is None)
    if near_missing:
        return _emit({"ok": False, "error": "near-lat 和 near-lng 需要一起提供"}, 2)
    if args.radius_km is not None and args.near_lat is None:
        return _emit({"ok": False, "error": "radius-km 需要和 near-lat、near-lng 一起使用"}, 2)
    if args.limit is not None and args.limit < 1:
        return _emit({"ok": False, "error": "limit 需要是正整数"}, 2)
    origin = (args.near_lat, args.near_lng) if args.near_lat is not None else None
    sort = args.sort or ("distance" if origin else "price")
    if sort == "distance" and origin is None:
        return _emit({"ok": False, "error": "按距离排序需要 near-lat 和 near-lng"}, 2)

    try:
        rows = fetch_atour_prices(
            args.city,
            args.check_in,
            args.check_out,
            scope="city",
            enrich_open_date=False,
        )
    except ValueError as exc:
        return _emit({"ok": False, "error": str(exc)}, 2)
    except AtourAPIError as exc:
        return _emit({"ok": False, "error": str(exc)}, 1)

    rows = _dedupe(rows)
    if args.brand:
        rows = [row for row in rows if _keep_brand(row, args.brand.strip())]
    if origin:
        for row in rows:
            lat, lng = row.get("latitude"), row.get("longitude")
            if lat is None or lng is None:
                row["_distance_km"] = None
            else:
                row["_distance_km"] = round(_haversine_km(origin[0], origin[1], lat, lng), 2)
        if args.radius_km is not None:
            rows = [
                row for row in rows
                if row.get("_distance_km") is not None and row["_distance_km"] <= args.radius_km
            ]
    if rows:
        enrich_open_dates(rows)

    hotels = [_hotel_record(row, origin is not None) for row in rows]
    _sort_hotels(hotels, sort)
    if args.limit is not None:
        hotels = hotels[: args.limit]
    missing = sum(1 for hotel in hotels if not hotel["open_date"])
    return _emit({
        "ok": True,
        "query": {
            "city": args.city,
            "check_in": args.check_in.isoformat(),
            "check_out": args.check_out.isoformat(),
            "brand": args.brand or "",
            "near": {"latitude": origin[0], "longitude": origin[1]} if origin else None,
            "radius_km": args.radius_km,
            "sort": sort,
            "limit": args.limit,
        },
        "count": len(hotels),
        "open_date_missing": missing,
        "price_note": _PRICE_NOTE,
        "hotels": hotels,
    })


def _rooms(args: argparse.Namespace) -> int:
    if args.check_in >= args.check_out:
        return _emit({"ok": False, "error": "退房日期必须晚于入住日期"}, 2)
    chain_id: object = int(args.chain_id) if str(args.chain_id).isdigit() else args.chain_id
    rooms = get_hotel_rooms(chain_id, args.check_in, args.check_out)
    return _emit({
        "ok": True,
        "chain_id": chain_id,
        "check_in": args.check_in.isoformat(),
        "check_out": args.check_out.isoformat(),
        "count": len(rooms),
        "price_note": _ROOM_PRICE_NOTE,
        "rooms": [_room_record(room) for room in rooms],
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="查询亚朵酒店，向标准输出打印 JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    cities = sub.add_parser("cities", help="列出已开业城市")
    cities.add_argument("--province", default="", help="只看一个省，例如 浙江 或 浙江省")
    cities.set_defaults(func=_cities)

    search = sub.add_parser("search", help="按一个城市和入住日期查询。城市越小越快")
    search.add_argument("--city", required=True, help="一个城市，例如 杭州 或 杭州市")
    search.add_argument("--check-in", required=True, type=_parse_date)
    search.add_argument("--check-out", required=True, type=_parse_date)
    search.add_argument("--brand", default="", help="品牌或名称片段，例如 轻居、亚朵X、亚朵S")
    search.add_argument("--near-lat", type=float, help="周边圆心纬度，国测局坐标 GCJ-02")
    search.add_argument("--near-lng", type=float, help="周边圆心经度，国测局坐标 GCJ-02")
    search.add_argument("--radius-km", type=float, help="只保留直线距离以内的店，并在查开业时间前生效")
    search.add_argument(
        "--sort",
        choices=("price", "open_date", "distance", "score"),
        default="",
        help="默认按展示价；给了坐标时默认按距离。open_date 为较新的在前",
    )
    search.add_argument("--limit", type=int, help="在开业时间补全和排序之后截断条数，不会少发开业时间请求")
    search.set_defaults(func=_search)

    rooms = sub.add_parser("rooms", help="按酒店编号查房型价")
    rooms.add_argument("--chain-id", required=True)
    rooms.add_argument("--check-in", required=True, type=_parse_date)
    rooms.add_argument("--check-out", required=True, type=_parse_date)
    rooms.set_defaults(func=_rooms)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
