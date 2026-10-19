"""Every APK finding has positive and negative evidence (§6.3), for an APK and for a project (§5.1)."""

import json

import pytest
from conftest import (
    TEST_ID,
    UNIT_ID,
    ad_data,
    config_data,
    make_apk_facts,
    make_placement,
    make_project_facts,
    make_spec,
)

from apkverify.model import FallbackAsset, Finding, Severity
from apkverify.process.static.apk_checks import check, code_config_state, code_space_state

CASES = (
    (
        "APK-LIB-KEYS",
        "key",
        Severity.ERROR,
        (),
        "Không thấy key Remote Config 'admob_id' trong code: APK không dùng thư viện quảng cáo mà tool biết, "
        "kết quả kiểm tra không đáng tin.",
    ),
    (
        "APK-NO-APPID",
        "none",
        Severity.ERROR,
        (),
        "APK thiếu meta-data com.google.android.gms.ads.APPLICATION_ID: app sẽ crash khi khởi tạo AdMob.",
    ),
    (
        "APK-TEST-APPID",
        "test_app",
        Severity.ERROR,
        (),
        "APK đang dùng App ID test của Google (ca-app-pub-3940256099942544~3347511713).",
    ),
    ("APK-TEST-UNIT", "test_unit", Severity.WARN, (), f"Code chứa ID test của Google: {TEST_ID}."),
    (
        "APK-SPACE-MISSING",
        "space",
        Severity.ERROR,
        (5,),
        f"Code không gọi Ad Space 'home_bottom_native' (dòng 5): ID {UNIT_ID} sẽ không bao giờ được request."
        " Gần giống: 'home_bottom_nativ'.",
    ),
    (
        "APK-CONFIG-MISSING",
        "config",
        Severity.ERROR,
        (5,),
        "Code không gọi config 'home_bottom' (dòng 5): vị trí này không có trong app. Gần giống: 'home_botto'.",
    ),
    (
        "APK-FALLBACK-EMPTY",
        "empty",
        Severity.WARN,
        (),
        "assets/admob_id.txt rỗng: nếu key admob_id trên Firebase rỗng, app không có ID quảng cáo nào.",
    ),
    ("APK-FALLBACK-DIFF", "different", Severity.WARN, (5,), "assets/admob_id.txt khác spec ở: home_bottom_native."),
)


@pytest.mark.parametrize("code,change,severity,rows,message", CASES)
def test_finding(code: str, change: str, severity: Severity, rows: tuple[int, ...], message: str) -> None:
    base = make_apk_facts()
    overrides = {}
    if change in {"key", "space", "config", "test_unit"}:
        strings = set(base.dex_strings)
        if change == "test_unit":
            strings.add(TEST_ID)
        else:
            old, new = {
                "key": ("admob_id", "unrelated"),
                "space": ("home_bottom_native", "home_bottom_nativ"),
                "config": ("home_bottom", "home_botto"),
            }[change]
            strings.remove(old)
            strings.add(new)
        overrides["dex_strings"] = frozenset(strings)
    elif change in {"none", "test_app"}:
        overrides["admob_app_id"] = None if change == "none" else "ca-app-pub-3940256099942544~3347511713"
    else:
        text = "" if change == "empty" else json.dumps(ad_data(listAds=[]))
        overrides["fallbacks"] = (FallbackAsset("admob_id", True, text), base.fallbacks[1])
    findings = check(make_spec(), make_apk_facts(**overrides))
    assert [f for f in findings if f.code == code] == [Finding(code, severity, message, rows)]


@pytest.mark.parametrize("code", [case[0] for case in CASES])
def test_absent(code: str) -> None:
    assert code not in {f.code for f in check(make_spec(), make_apk_facts())}


@pytest.mark.parametrize("text", ["not json", "{}", '{"listConfig":[]}'])
def test_invalid_or_missing_fallback_config(text: str) -> None:
    base = make_apk_facts()
    apk = make_apk_facts(fallbacks=(base.fallbacks[0], FallbackAsset("config_show_ads", True, text)))
    assert [f for f in check(make_spec(), apk) if f.code == "APK-FALLBACK-DIFF"] == [
        Finding("APK-FALLBACK-DIFF", Severity.WARN, "assets/config_show_ads.txt khác spec ở: home_bottom.", (5,))
    ]


@pytest.mark.parametrize("text", ["", " "])
def test_missing_and_empty_config_fallback(text: str) -> None:
    apk = make_apk_facts(fallbacks=(make_apk_facts().fallbacks[0], FallbackAsset("config_show_ads", True, text)))
    expected = Finding(
        "APK-FALLBACK-EMPTY",
        Severity.WARN,
        "assets/config_show_ads.txt rỗng: "
        "nếu fetch Remote Config lỗi hoặc key rỗng, không vị trí nào có config nên không quảng cáo nào show.",
    )
    assert [f for f in check(make_spec(), apk) if f.code == expected.code] == [expected]
    assert expected in check(make_spec(), make_apk_facts(fallbacks=(apk.fallbacks[0],)))


def test_fallback_config_only_requires_presence() -> None:
    base = make_apk_facts()
    data = config_data(listConfig=[dict(configName="home_bottom", isOn=False, type="other")])
    apk = make_apk_facts(fallbacks=(base.fallbacks[0], FallbackAsset("config_show_ads", True, json.dumps(data))))
    assert "APK-FALLBACK-DIFF" not in {f.code for f in check(make_spec(), apk)}


def test_test_ids_sorted_and_limited() -> None:
    ids = [f"ca-app-pub-3940256099942544/{i:010}" for i in range(9, 0, -1)]
    apk = make_apk_facts(dex_strings=make_apk_facts().dex_strings | frozenset(ids))
    assert [f.message for f in check(make_spec(), apk) if f.code == "APK-TEST-UNIT"] == [
        f"Code chứa ID test của Google: {', '.join(sorted(ids)[:5])}."
    ]


def test_grouped_config_and_case_sensitive_states() -> None:
    spec = make_spec(make_placement(), make_placement(row=6))
    apk = make_apk_facts(dex_strings=frozenset({"admob_id", "config_show_ads", "Home_bottom"}))
    missing = [f for f in check(spec, apk) if f.code == "APK-CONFIG-MISSING"]
    assert len(missing) == 1 and missing[0].rows == (5, 6)
    assert code_config_state(spec.placements[0], apk) == "THIẾU"
    assert code_space_state(make_placement(), apk) == "THIẾU"
    assert code_config_state(make_placement(config_name=""), apk) == "—"
    assert code_space_state(make_placement(ad_id=""), apk) == "—"
    assert code_space_state(make_placement(), make_apk_facts()) == "OK"
    assert code_config_state(make_placement(), make_apk_facts()) == "OK"


# --- project facts (static-check-spec §5.1) ---


def test_project_lib_keys_accept_a_declared_library() -> None:
    strings = frozenset({"home_bottom", "home_bottom_native"})
    declared = make_project_facts(dex_strings=strings, project={"ad_library": "com.github.piontech96:Dolphin-Ads:1"})
    assert "APK-LIB-KEYS" not in {f.code for f in check(make_spec(), declared)}
    missing = [f for f in check(make_spec(), make_project_facts(dex_strings=strings)) if f.code == "APK-LIB-KEYS"]
    assert [f.message for f in missing] == [
        f"Không thấy key Remote Config '{key}' trong code của project, và project không khai báo thư viện quảng cáo "
        "mà tool biết (com.github.piontech96:Dolphin-Ads): kết quả kiểm tra không đáng tin."
        for key in ("admob_id", "config_show_ads")
    ]


def test_project_app_id_messages() -> None:
    absent = [f.message for f in check(make_spec(), make_project_facts(admob_app_id=None)) if f.code == "APK-NO-APPID"]
    assert absent == [
        "Project thiếu meta-data com.google.android.gms.ads.APPLICATION_ID trong AndroidManifest.xml: "
        "app sẽ crash khi khởi tạo AdMob."
    ]
    test_app = make_project_facts(admob_app_id="ca-app-pub-3940256099942544~3347511713")
    assert [f.message for f in check(make_spec(), test_app) if f.code == "APK-TEST-APPID"] == [
        "Project đang dùng App ID test của Google (ca-app-pub-3940256099942544~3347511713)."
    ]


def test_project_fallback_path_in_message() -> None:
    fallbacks = (
        FallbackAsset("admob_id", False, "", "app/src/main/assets/admob_id.txt"),
        FallbackAsset("config_show_ads", True, "not json", "LibAds/src/main/assets/config_show_ads.txt"),
    )
    messages = [f.message for f in check(make_spec(), make_project_facts(fallbacks=fallbacks))]
    assert (
        "app/src/main/assets/admob_id.txt rỗng: nếu key admob_id trên Firebase rỗng, app không có ID quảng cáo nào."
        in messages
    )
    assert "LibAds/src/main/assets/config_show_ads.txt khác spec ở: home_bottom." in messages


@pytest.mark.parametrize(
    "unresolved,message",
    [
        (
            ("package", "libs.versions.appId.get()"),
            "Không đọc được applicationId trong project (libs.versions.appId.get()): bỏ qua RC-PACKAGE-MISMATCH.",
        ),
        (
            ("admob_app_id", "${admobAppId}"),
            "Không đọc được AdMob App ID trong project (${admobAppId}): bỏ qua RC-APPID-MISMATCH, APK-TEST-APPID.",
        ),
    ],
)
def test_project_unresolved(unresolved: tuple[str, str], message: str) -> None:
    apk = make_project_facts(project={"unresolved": (unresolved,)})
    assert [f for f in check(make_spec(), apk) if f.code == "PRJ-UNRESOLVED"] == [
        Finding("PRJ-UNRESOLVED", Severity.WARN, message)
    ]


def test_project_unresolved_absent() -> None:
    assert "PRJ-UNRESOLVED" not in {f.code for f in check(make_spec(), make_project_facts())}
    assert "PRJ-UNRESOLVED" not in {f.code for f in check(make_spec(), make_apk_facts())}


def test_unresolved_app_id_is_not_checked_for_test_ids() -> None:
    apk = make_project_facts(
        admob_app_id="ca-app-pub-3940256099942544~3347511713",
        project={"unresolved": (("admob_app_id", "@string/x"),)},
    )
    assert "APK-TEST-APPID" not in {f.code for f in check(make_spec(), apk)}
