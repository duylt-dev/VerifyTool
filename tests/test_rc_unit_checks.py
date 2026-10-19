"""Ad unit finding messages, severities and rows (static-check-spec §6.2)."""

import json

import pytest
from conftest import APP_ID, OTHER_ID, TEST_ID, UNIT_ID, ad_data, config_data, make_apk_facts, make_spec

from apkverify.checks.rc_checks import check
from apkverify.model import Finding, RcValue, Severity

CASES = (
    (
        "RC-SPACE-MISSING",
        "rename",
        Severity.ERROR,
        (5,),
        "Thiếu ID: Ad Space 'home_bottom_native' (dòng 5) không có trong 'admob_id'. Gần giống: 'home_bottom_nativ'.",
    ),
    (
        "RC-ID-MISMATCH",
        "id",
        Severity.ERROR,
        (5,),
        f"Sai ID: 'home_bottom_native' trên Remote Config là {OTHER_ID}, spec là {UNIT_ID}.",
    ),
    (
        "RC-ID-EMPTY",
        "empty",
        Severity.ERROR,
        (5,),
        "ID rỗng: 'home_bottom_native' có trong 'admob_id' nhưng id rỗng, thư viện sẽ bỏ qua.",
    ),
    ("RC-ID-TEST", "test", Severity.ERROR, (5,), f"'home_bottom_native' đang dùng ID test của Google ({TEST_ID})."),
    ("RC-ID-FORMAT", "format", Severity.ERROR, (5,), "'home_bottom_native': ID 'bad' sai định dạng AdMob."),
    (
        "RC-PUBLISHER",
        "publisher",
        Severity.ERROR,
        (5,),
        "'home_bottom_native': ID thuộc publisher 2222222222222222, App ID thuộc 1111111111111111.",
    ),
    (
        "RC-APPID-MISMATCH",
        "app",
        Severity.ERROR,
        (),
        f"App ID trên Remote Config (other) khác App ID trong APK ({APP_ID}).",
    ),
    (
        "RC-PACKAGE-MISMATCH",
        "package",
        Severity.ERROR,
        (),
        "Package trên Remote Config (other) khác package APK (com.example.mini).",
    ),
    (
        "RC-TYPE-MISMATCH",
        "type",
        Severity.WARN,
        (5,),
        "'home_bottom_native': adsType 'banner' không khớp Định Dạng 'Native' của spec.",
    ),
    (
        "RC-SPACE-EXTRA",
        "extra",
        Severity.WARN,
        (),
        "Thừa: Ad Space 'extra' có trên Remote Config nhưng không có trong spec.",
    ),
    (
        "RC-DUP-SPACE",
        "duplicate",
        Severity.WARN,
        (5,),
        "Ad Space 'home_bottom_native' xuất hiện 2 lần trên Remote Config.",
    ),
)


def values(data: dict) -> tuple[RcValue, ...]:
    return (
        RcValue("admob_id", json.dumps(data), "admob_id.json"),
        RcValue("config_show_ads", json.dumps(config_data()), "config_show_ads.json"),
    )


@pytest.mark.parametrize("code,change,severity,rows,message", CASES)
def test_finding(code: str, change: str, severity: Severity, rows: tuple[int, ...], message: str) -> None:
    data = ad_data()
    unit = data["listAds"][0]
    if change in {"id", "empty", "test", "format", "publisher"}:
        unit["id"] = {
            "id": OTHER_ID,
            "empty": "",
            "test": TEST_ID,
            "format": "bad",
            "publisher": "ca-app-pub-2222222222222222/3333333333",
        }[change]
    elif change == "rename":
        unit["spaceName"] = "home_bottom_nativ"
    elif change == "app":
        data["appId"] = "other"
    elif change == "package":
        data["package"] = "other"
    elif change == "type":
        unit["adsType"] = "banner"
    elif change in {"extra", "duplicate"}:
        data["listAds"].append(dict(unit, spaceName="extra" if change == "extra" else unit["spaceName"]))
    findings = check(make_spec(), values(data), make_apk_facts())
    assert [f for f in findings if f.code == code] == [Finding(code, severity, message, rows)]


@pytest.mark.parametrize("code", [case[0] for case in CASES])
def test_absent(code: str) -> None:
    assert code not in {f.code for f in check(make_spec(), values(ad_data()), make_apk_facts())}


def test_test_app_id_and_non_admob_test_unit() -> None:
    data = ad_data(appId="ca-app-pub-3940256099942544~3347511713")
    remote = (
        *values(data),
        RcValue(
            "pangle_id",
            json.dumps(ad_data(listAds=[dict(spaceName="home_bottom_native", adsType="native", id=TEST_ID)])),
            "pangle_id.json",
        ),
    )
    findings = [f for f in check(make_spec(), remote, make_apk_facts()) if f.code == "RC-ID-TEST"]
    assert findings == [
        Finding(
            "RC-ID-TEST",
            Severity.ERROR,
            "'admob_id.appId' đang dùng ID test của Google (ca-app-pub-3940256099942544~3347511713).",
        ),
        Finding("RC-ID-TEST", Severity.ERROR, f"'home_bottom_native' đang dùng ID test của Google ({TEST_ID}).", (5,)),
    ]


def test_duplicate_across_networks() -> None:
    remote = (*values(ad_data()), RcValue("gam_id", json.dumps(ad_data()), "gam_id.json"))
    duplicate = [f for f in check(make_spec(), remote, make_apk_facts()) if f.code == "RC-DUP-SPACE"]
    assert duplicate == [
        Finding(
            "RC-DUP-SPACE", Severity.WARN, "Ad Space 'home_bottom_native' xuất hiện 2 lần trên Remote Config.", (5,)
        )
    ]


@pytest.mark.parametrize("empty", ["", None])
def test_empty_or_null_id_is_only_rc_id_empty(empty: str | None) -> None:
    # Review fix 2026-10-05: an empty id also raised RC-ID-FORMAT, and `"id": null` crashed the checks.
    data = ad_data()
    data["listAds"][0]["id"] = empty
    codes = [f.code for f in check(make_spec(), values(data), make_apk_facts())]
    assert "RC-ID-EMPTY" in codes
    assert "RC-ID-FORMAT" not in codes
