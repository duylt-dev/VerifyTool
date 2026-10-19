"""Real RC files (static-check-spec §4)."""

from pathlib import Path

import pytest
from conftest import UNIT_ID, ad_data, config_data, write_rc

from apkverify.errors import InputError
from apkverify.input.rc_reader import read_rc_files
from apkverify.model import AdUnit, PlacementConfig, RcValue
from apkverify.process.rc_parse import parse_ad_unit_list, parse_ads_config


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
