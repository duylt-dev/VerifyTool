"""Pure parsers for Remote Config values (static-check-spec §4).

They live in the process step, not in `input/rc_reader.py`, because a value that does not parse is a finding
(RC-JSON-INVALID), not an input error.
"""

import json

from apkverify.errors import RcFormatError
from apkverify.model import AdsConfig, AdUnit, AdUnitList, PlacementConfig


def _str(value: object) -> str:
    """A missing or null JSON field is ""; anything else is its text (`"id": null` must not crash a check)."""
    return "" if value is None else str(value)


def _parse(text: str, field: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError as error:
        raise RcFormatError(f"JSON không hợp lệ: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise RcFormatError(f"thiếu {field}")
    return data


def parse_ad_unit_list(key: str, text: str) -> AdUnitList:
    data = _parse(text, "listAds")
    units = []
    for i, item in enumerate(data["listAds"], 1):
        if not isinstance(item, dict) or not isinstance(item.get("spaceName"), str) or not item["spaceName"]:
            raise RcFormatError(f"phần tử thứ {i} không có spaceName")
        buffer = item.get("buffer")
        units.append(
            AdUnit(
                item["spaceName"],
                _str(item.get("adsType")),
                _str(item.get("id")),
                buffer if type(buffer) is int else None,
            )
        )
    return AdUnitList(key, _str(data.get("network")), _str(data.get("appId")), _str(data.get("package")), tuple(units))


def parse_ads_config(text: str) -> AdsConfig:
    data = _parse(text, "listConfig")
    configs = []
    for i, item in enumerate(data["listConfig"], 1):
        if not isinstance(item, dict) or not isinstance(item.get("configName"), str) or not item["configName"]:
            raise RcFormatError(f"phần tử thứ {i} không có configName")
        configs.append(PlacementConfig(item["configName"], item.get("isOn") is True, _str(item.get("type"))))
    flags = tuple((k, v) for k, v in data.items() if k.startswith("disable") and isinstance(v, bool))
    return AdsConfig(flags, tuple(configs))
