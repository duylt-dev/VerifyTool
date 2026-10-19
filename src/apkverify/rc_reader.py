"""Remote Config file reader and pure value parsers (static-check-spec §4)."""

import json
from collections.abc import Sequence
from pathlib import Path

from apkverify.errors import InputError, RcFormatError
from apkverify.model import AdsConfig, AdUnit, AdUnitList, PlacementConfig, RcValue


def read_rc_files(paths: Sequence[Path]) -> tuple[RcValue, ...]:
    values: dict[str, RcValue] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise InputError(f"Không đọc được file Remote Config {path.name}: {error}.") from error
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        entries = []
        if isinstance(data, dict) and ("parameters" in data or "parameterGroups" in data):
            parameters = list(data.get("parameters", {}).items())
            for group in data.get("parameterGroups", {}).values():
                parameters.extend(group.get("parameters", {}).items())
            for key, parameter in parameters:
                default = parameter.get("defaultValue", {})
                value = "" if default.get("useInAppDefault") else default.get("value", "")
                entries.append(RcValue(key, value, path.name, tuple(parameter.get("conditionalValues", {}))))
        else:
            entries.append(RcValue(path.stem, text, path.name))
        for entry in entries:
            if entry.key in values:
                raise InputError(
                    f"Key Remote Config '{entry.key}' có ở hai file: {values[entry.key].source}, {path.name}."
                )
            values[entry.key] = entry
    return tuple(values[k] for k in sorted(values))


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
