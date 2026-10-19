"""Pure Remote Config value parsing (static-check-spec §4)."""

import json

import pytest
from conftest import APP_ID, ad_data

from apkverify.errors import RcFormatError
from apkverify.model import AdUnit, PlacementConfig
from apkverify.process.rc_parse import parse_ad_unit_list, parse_ads_config


def test_unit_fields_defaults_and_buffer() -> None:
    data = ad_data(
        listAds=[
            dict(spaceName="one", buffer=3),
            dict(spaceName="two", buffer="3"),
            dict(spaceName="three", buffer=True),
        ]
    )
    parsed = parse_ad_unit_list("gam_id", json.dumps(data))
    assert (parsed.key, parsed.network, parsed.app_id, parsed.package) == (
        "gam_id",
        "google",
        APP_ID,
        "com.example.mini",
    )
    assert parsed.units == (AdUnit("one", "", "", 3), AdUnit("two", "", ""), AdUnit("three", "", ""))
    empty = parse_ad_unit_list("admob_id", '{"listAds":[]}')
    assert (empty.network, empty.app_id, empty.package, empty.units) == ("", "", "", ())


def test_config_flags_and_missing_values() -> None:
    parsed = parse_ads_config(
        json.dumps(
            dict(
                disableNative=False,
                other=True,
                disableAllConfig=True,
                disableBanner=1,
                listConfig=[dict(configName="one"), dict(configName="two", isOn="false")],
            )
        )
    )
    assert parsed.flags == (("disableNative", False), ("disableAllConfig", True))
    assert parsed.configs == (PlacementConfig("one", False, ""), PlacementConfig("two", False, ""))


@pytest.mark.parametrize(
    "text,reason",
    [
        ("{}", "thiếu listAds"),
        ("[]", "thiếu listAds"),
        ('{"listAds":{}}', "thiếu listAds"),
        ('{"listAds":[{}]}', "phần tử thứ 1 không có spaceName"),
        ('{"listAds":[null]}', "phần tử thứ 1 không có spaceName"),
    ],
)
def test_invalid_units(text: str, reason: str) -> None:
    with pytest.raises(RcFormatError) as error:
        parse_ad_unit_list("admob_id", text)
    assert str(error.value) == reason


@pytest.mark.parametrize(
    "text,reason",
    [
        ("{}", "thiếu listConfig"),
        ("null", "thiếu listConfig"),
        ('{"listConfig":{}}', "thiếu listConfig"),
        ('{"listConfig":[{}]}', "phần tử thứ 1 không có configName"),
        ('{"listConfig":[null]}', "phần tử thứ 1 không có configName"),
    ],
)
def test_invalid_configs(text: str, reason: str) -> None:
    with pytest.raises(RcFormatError) as error:
        parse_ads_config(text)
    assert str(error.value) == reason


@pytest.mark.parametrize("kind", ["unit", "config"])
def test_invalid_json(kind: str) -> None:
    with pytest.raises(RcFormatError) as error:
        if kind == "unit":
            parse_ad_unit_list("admob_id", "not json")
        else:
            parse_ads_config("not json")
    assert str(error.value) == "JSON không hợp lệ: Expecting value: line 1 column 1 (char 0)"
