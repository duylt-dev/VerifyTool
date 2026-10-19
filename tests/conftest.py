"""Real-file builders and pure value builders for static tests (§9)."""

import json
import unicodedata
from pathlib import Path

import openpyxl
import pytest

from apkverify.model import AdEvent, ApkFacts, FallbackAsset, Placement, Spec

ROOT = Path(__file__).resolve().parents[1]
MINI_APK = ROOT / "tests/fixtures/mini.apk"
APP_ID = "ca-app-pub-1111111111111111~2222222222"
UNIT_ID = "ca-app-pub-1111111111111111/3333333333"
OTHER_ID = "ca-app-pub-1111111111111111/4444444444"
TEST_ID = "ca-app-pub-3940256099942544/6300978111"
HEADERS = (
    "STT",
    "Task",
    "Trạng thái",
    "Định Dạng",
    "Config Name",
    "Ad Space",
    "Network Ad Name",
    "ID",
    "Ghi chú AD",
    "Mã task",
    "Link ClickUp",
)
REAL_FILES = (
    "SpinWheel2_dev_1.0.1-release.apk",
    "Quang_cao_Ads_Spin_wheel_2.xlsx",
    "admob_id.json",
    "config_show_ads.json",
)


def make_spec_xlsx(path: Path, rows: list[dict], *, nfd_header: bool = False) -> Path:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Ads"
    sheet.append(["Quảng Cáo / Ads_Test"])
    sheet.append(["Nguồn: test"])
    sheet.append([])
    sheet.append([unicodedata.normalize("NFD", h) if nfd_header else h for h in HEADERS])
    for row in rows:
        sheet.append([row.get(header) for header in HEADERS])
    workbook.save(path)
    workbook.close()
    return path


def write_rc(
    path: Path, value: object, *, template: bool = False, grouped: bool = False, conditions: tuple[str, ...] = ()
) -> Path:
    if template:
        parameters = {
            key: {
                "defaultValue": {"value": json.dumps(data, ensure_ascii=False)},
                "conditionalValues": {c: {"value": "conditional"} for c in conditions},
            }
            for key, data in value.items()
        }
        value = {"parameterGroups": {"ads": {"parameters": parameters}}} if grouped else {"parameters": parameters}
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def make_placement(**overrides: object) -> Placement:
    fields = dict(
        row=5,
        group="Home",
        group_note="",
        task="",
        status="",
        format="Native",
        config_name="home_bottom",
        space_name="home_bottom_native",
        network_name="Am_home_bottom_native",
        ad_id=UNIT_ID,
        note="",
        task_code="",
        link="",
    )
    fields.update(overrides)
    return Placement(**fields)


def make_spec(*placements: Placement) -> Spec:
    return Spec("spec.xlsx", "Ads", "Quảng Cáo / Ads_Test", placements or (make_placement(),))


def ad_data(**overrides: object) -> dict:
    fields = dict(
        network="google",
        appId=APP_ID,
        package="com.example.mini",
        listAds=[dict(spaceName="home_bottom_native", adsType="native", id=UNIT_ID)],
    )
    fields.update(overrides)
    return fields


def config_data(**overrides: object) -> dict:
    fields = dict(listConfig=[dict(configName="home_bottom", isOn=True, type="native")])
    fields.update(overrides)
    return fields


def make_apk_facts(**overrides: object) -> ApkFacts:
    fields = dict(
        file_name="mini.apk",
        sha256="a" * 64,
        size=100,
        package="com.example.mini",
        version_name="1.0-mini",
        version_code="7",
        admob_app_id=APP_ID,
        firebase_project_id="mini-project",
        firebase_app_id="1:123456789012:android:0123456789abcdef",
        firebase_sender_id="123456789012",
        fallbacks=(
            FallbackAsset("admob_id", True, json.dumps(ad_data())),
            FallbackAsset("config_show_ads", True, json.dumps(config_data())),
        ),
        dex_strings=frozenset({"admob_id", "config_show_ads", "home_bottom", "home_bottom_native"}),
    )
    fields.update(overrides)
    return ApkFacts(**fields)


def make_event(**overrides: object) -> AdEvent:
    fields = dict(
        time=1000.0,
        event="show success",
        source="native",
        names=("home_bottom", "home_bottom_native"),
        ad_unit=UNIT_ID,
        code="",
        message="",
        structured=True,
    )
    fields.update(overrides)
    return AdEvent(**fields)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    missing = [name for name in REAL_FILES if not (ROOT / "input" / name).is_file()]
    if missing:
        marker = pytest.mark.skip(reason="Thiếu input thực: " + ", ".join(missing))
        for item in items:
            if "real_input" in item.keywords:
                item.add_marker(marker)
