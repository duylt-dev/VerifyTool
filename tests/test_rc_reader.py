"""Real RC files and pure value parsing (static-check-spec §4)."""

import json
from pathlib import Path

import pytest
from conftest import APP_ID, UNIT_ID, ad_data, config_data, write_rc

from apkverify.errors import InputError, RcFormatError
from apkverify.model import AdUnit, PlacementConfig, RcValue
from apkverify.rc_reader import parse_ad_unit_list, parse_ads_config, read_rc_files


@pytest.mark.parametrize("template,grouped", [(False, False), (True, False), (True, True)])
def test_file_shapes(tmp_path: Path, template: bool, grouped: bool) -> None:
    if template:
        paths = [
            write_rc(
                tmp_path / "export.json",
                {"config_show_ads": config_data(), "admob_id": ad_data()},
                template=True,
                grouped=grouped,
                conditions=("country", "version"),
            )
        ]
    else:
        paths = [
            write_rc(tmp_path / "config_show_ads.json", config_data()),
            write_rc(tmp_path / "admob_id.json", ad_data()),
        ]
    values = read_rc_files(paths)
    assert [v.key for v in values] == ["admob_id", "config_show_ads"]
    assert parse_ad_unit_list(values[0].key, values[0].value).units == (
        AdUnit("home_bottom_native", "native", UNIT_ID),
    )
    assert parse_ads_config(values[1].value).configs == (PlacementConfig("home_bottom", True, "native"),)
    assert values[0].conditions == (("country", "version") if template else ())


def test_template_merges_groups_and_in_app_default(tmp_path: Path) -> None:
    path = write_rc(
        tmp_path / "template.json",
        {
            "parameters": {"z": {"defaultValue": {"value": "text"}}},
            "parameterGroups": {
                "g": {"parameters": {"a": {"defaultValue": {"useInAppDefault": True, "value": "ignored"}}, "b": {}}}
            },
        },
    )
    assert read_rc_files([path]) == (
        RcValue("a", "", "template.json"),
        RcValue("b", "", "template.json"),
        RcValue("z", "text", "template.json"),
    )


@pytest.mark.parametrize("raw", ["broken JSON", "[]", "null", '{"listAds":[]}'])
def test_non_template_preserves_raw_text_and_bom(tmp_path: Path, raw: str) -> None:
    path = tmp_path / "admob_id.json"
    path.write_text(raw, encoding="utf-8-sig")
    assert read_rc_files([path]) == (RcValue("admob_id", raw, path.name),)


def test_duplicate_key(tmp_path: Path) -> None:
    first = write_rc(tmp_path / "admob_id.json", ad_data())
    second = write_rc(tmp_path / "export.json", {"admob_id": ad_data()}, template=True)
    with pytest.raises(InputError) as error:
        read_rc_files([first, second])
    assert str(error.value) == "Key Remote Config 'admob_id' có ở hai file: admob_id.json, export.json."


def test_unreadable_file(tmp_path: Path) -> None:
    path = tmp_path / "absent.json"
    with pytest.raises(InputError) as error:
        read_rc_files([path])
    assert str(error.value).startswith("Không đọc được file Remote Config absent.json: ")
    assert str(error.value).endswith(".")


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
