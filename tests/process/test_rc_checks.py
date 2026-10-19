"""Loading failures, row attribution and RC states (§6.2, §7)."""

import json

import pytest
from conftest import OTHER_ID, TEST_ID, UNIT_ID, ad_data, config_data, make_apk_facts, make_placement, make_spec

from apkverify.model import Finding, RcValue, Severity
from apkverify.process.rc_parse import parse_ad_unit_list, parse_ads_config
from apkverify.process.static.rc_checks import check, load_config, load_lists, rc_config_state, rc_id_state


def values() -> tuple[RcValue, ...]:
    return (
        RcValue("admob_id", json.dumps(ad_data()), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(config_data()), "config_show_ads.json"),
    )


@pytest.mark.parametrize("key", ["admob_id", "config_show_ads"])
@pytest.mark.parametrize("text", [None, "", "  "])
def test_required_missing(key: str, text: str | None) -> None:
    remote = [v for v in values() if v.key != key]
    if text is not None:
        remote.append(RcValue(key, text, "file.json"))
    findings = check(make_spec(), remote, make_apk_facts())
    assert [f for f in findings if f.code == "RC-KEY-MISSING"] == [
        Finding(
            "RC-KEY-MISSING",
            Severity.ERROR,
            f"Không có giá trị Remote Config '{key}' (thiếu trên Firebase hoặc chưa export vào input/).",
            (5,),
        )
    ]
    assert "RC-SPACE-MISSING" not in {f.code for f in findings}
    assert "RC-CONFIG-MISSING" not in {f.code for f in findings}


@pytest.mark.parametrize(
    "key,field,rows",
    [
        ("admob_id", "listAds", (5,)),
        ("gam_id", "listAds", ()),
        ("pangle_id", "listAds", ()),
        ("config_show_ads", "listConfig", (5,)),
    ],
)
def test_invalid_shape(key: str, field: str, rows: tuple[int, ...]) -> None:
    remote = [v for v in values() if v.key != key] + [RcValue(key, "{}", "file.json")]
    findings = check(make_spec(), remote, make_apk_facts())
    assert [f for f in findings if f.code == "RC-JSON-INVALID"] == [
        Finding(
            "RC-JSON-INVALID", Severity.ERROR, f"Giá trị Remote Config '{key}' không đọc được: thiếu {field}.", rows
        )
    ]


def test_conditional_only_known_keys() -> None:
    remote = (
        *values(),
        RcValue("gam_id", "", "file.json", ("country", "version")),
        RcValue("other", "", "file.json", ("country",)),
    )
    findings = check(make_spec(), remote, make_apk_facts())
    assert [f for f in findings if f.code == "RC-CONDITIONAL"] == [
        Finding(
            "RC-CONDITIONAL",
            Severity.INFO,
            "'gam_id' có giá trị theo điều kiện (country, version); tool chỉ kiểm giá trị mặc định.",
        )
    ]


@pytest.mark.parametrize("code", ["RC-KEY-MISSING", "RC-JSON-INVALID", "RC-CONDITIONAL"])
def test_absent(code: str) -> None:
    assert code not in {f.code for f in check(make_spec(), values(), make_apk_facts())}


@pytest.mark.parametrize(
    "ids,expected",
    [
        ([], "THIẾU"),
        ([""], "RỖNG"),
        ([OTHER_ID], "SAI"),
        ([UNIT_ID], "OK"),
        ([OTHER_ID, UNIT_ID], "OK"),
        ([UNIT_ID, TEST_ID], "TEST"),
        (["", UNIT_ID], "OK"),
    ],
)
def test_id_state_precedence(ids: list[str], expected: str) -> None:
    data = ad_data(listAds=[dict(spaceName="home_bottom_native", id=ad_id) for ad_id in ids])
    lists = {"admob_id": parse_ad_unit_list("admob_id", json.dumps(data))}
    assert rc_id_state(make_placement(), lists) == expected
    assert rc_id_state(make_placement(ad_id=""), lists) == "—"


def test_admob_required_even_if_other_list_has_space() -> None:
    lists = {"gam_id": parse_ad_unit_list("gam_id", json.dumps(ad_data()))}
    assert rc_id_state(make_placement(), lists) == "THIẾU"


@pytest.mark.parametrize(
    "data,expected",
    [
        (None, "THIẾU"),
        (dict(listConfig=[]), "THIẾU"),
        (config_data(), "BẬT"),
        (dict(listConfig=[dict(configName="home_bottom")]), "TẮT"),
    ],
)
def test_config_state(data: dict | None, expected: str) -> None:
    config = parse_ads_config(json.dumps(data)) if data is not None else None
    assert rc_config_state(make_placement(), config) == expected
    assert rc_config_state(make_placement(config_name=""), config) == "—"


def test_loaders_and_missing_rows_follow_roles() -> None:
    lists, findings = load_lists(values())
    config, config_findings = load_config(values())
    assert lists["admob_id"].units[0].ad_id == UNIT_ID
    assert config.configs[0].is_on
    assert findings == config_findings == []
    spec = make_spec(make_placement(), make_placement(row=6, ad_id=""), make_placement(row=7, config_name=""))
    failures = [f for f in check(spec, (), make_apk_facts()) if f.code == "RC-KEY-MISSING"]
    assert [f.rows for f in failures] == [(5, 7), (5, 6)]
