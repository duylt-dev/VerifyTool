"""Placement-config findings (static-check-spec §6.2)."""

import json

import pytest
from conftest import ad_data, config_data, make_apk_facts, make_placement, make_spec

from apkverify.checks.rc_checks import check
from apkverify.model import Finding, RcValue, Severity

CASES = (
    (
        "RC-CONFIG-MISSING",
        "missing",
        Severity.ERROR,
        (5,),
        "Thiếu config: 'home_bottom' (dòng 5) không có trong config_show_ads; "
        "thư viện sẽ báo \"ad config not found\" và không show. Gần giống: 'home_botto'.",
    ),
    ("RC-CONFIG-OFF", "off", Severity.WARN, (5,), "Vị trí 'home_bottom' đang TẮT (isOn=false): sẽ không show."),
    ("RC-CONFIG-TYPE", "type", Severity.WARN, (5,), "Config 'home_bottom' có type 'banner', spec ghi 'Native'."),
    (
        "RC-CONFIG-EXTRA",
        "extra",
        Severity.WARN,
        (),
        "Thừa: config 'extra' có trên Remote Config nhưng không có trong spec.",
    ),
    ("RC-DISABLE-ALL", "all", Severity.WARN, (), "disableAllConfig = true: mọi quảng cáo bị tắt."),
    ("RC-DISABLE-TYPE", "native", Severity.WARN, (5,), "disableNative = true: các vị trí native sẽ không show."),
)


def values(data: dict) -> tuple[RcValue, ...]:
    return (
        RcValue("admob_id", json.dumps(ad_data()), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(data), "config_show_ads.json"),
    )


@pytest.mark.parametrize("code,change,severity,rows,message", CASES)
def test_finding(code: str, change: str, severity: Severity, rows: tuple[int, ...], message: str) -> None:
    data = config_data()
    config = data["listConfig"][0]
    if change == "missing":
        config["configName"] = "home_botto"
    elif change == "off":
        config["isOn"] = False
    elif change == "type":
        config["type"] = "banner"
    elif change == "extra":
        data["listConfig"].append(dict(config, configName="extra"))
    elif change == "all":
        data["disableAllConfig"] = True
    else:
        data["disableNative"] = True
    findings = check(make_spec(), values(data), make_apk_facts())
    assert [f for f in findings if f.code == code] == [Finding(code, severity, message, rows)]


@pytest.mark.parametrize("code", [case[0] for case in CASES])
def test_absent(code: str) -> None:
    assert code not in {f.code for f in check(make_spec(), values(config_data()), make_apk_facts())}


def test_grouped_config_rows_and_format_union() -> None:
    spec = make_spec(make_placement(), make_placement(row=6, format="Open Ad"), make_placement(row=7, format="Unknown"))
    data = config_data(listConfig=[dict(configName="home_bottom", isOn=False, type="open_app")])
    findings = check(spec, values(data), make_apk_facts())
    off = [f for f in findings if f.code == "RC-CONFIG-OFF"]
    assert len(off) == 1 and off[0].rows == (5, 6, 7)
    assert "RC-CONFIG-TYPE" not in {f.code for f in findings}
    data["listConfig"][0]["type"] = "banner"
    mismatch = [f for f in check(spec, values(data), make_apk_facts()) if f.code == "RC-CONFIG-TYPE"]
    assert mismatch == [
        Finding(
            "RC-CONFIG-TYPE",
            Severity.WARN,
            "Config 'home_bottom' có type 'banner', spec ghi 'Native', 'Open Ad', 'Unknown'.",
            (5, 6, 7),
        )
    ]


def test_disable_type_uses_units_and_configs_not_unused_types() -> None:
    data = config_data(
        disableNative=True,
        disableOpenApp=True,
        disableBanner=True,
        listConfig=[dict(configName="home_bottom", isOn=True, type="open_app")],
    )
    findings = [f for f in check(make_spec(), values(data), make_apk_facts()) if f.code == "RC-DISABLE-TYPE"]
    assert {(f.message, f.rows) for f in findings} == {
        ("disableNative = true: các vị trí native sẽ không show.", (5,)),
        ("disableOpenApp = true: các vị trí open_app sẽ không show.", (5,)),
    }
