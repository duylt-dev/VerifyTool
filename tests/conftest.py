"""Real-file builders and pure value builders for static tests (§9)."""

import json
import unicodedata
from pathlib import Path

import openpyxl
import pytest

from apkverify.model import AdEvent, ApkFacts, FallbackAsset, Placement, ProjectInfo, Spec

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


def make_project_facts(**overrides: object) -> ApkFacts:
    """ApkFacts as `input/project_reader.py` returns them; `project=` overrides ProjectInfo fields by keyword."""
    info = dict(root="/work/Mini", app_module=":app", ad_library="", source_files=3, unresolved=())
    info.update(overrides.pop("project", {}))
    fields = dict(file_name="Mini", sha256="", size=0, project=ProjectInfo(**info))
    fields.update(overrides)
    return make_apk_facts(**fields)


APP_BUILD_KTS = """plugins {
    alias(libs.plugins.android.application) // not com.android.library
}
android {
    namespace = "com.example.ns"
    defaultConfig {
        applicationId = "com.example.mini" // the package
        versionCode = 7
        versionName = "1.0-mini"
    }
}
dependencies {
    implementation(project(":LibAds"))
    implementation("com.github.piontech96:Dolphin-Ads:1.0.4-alpha37-1")
}
"""
APP_KOTLIN = """package com.example

const val HOME = "home_bottom"

fun show() {
    showNative(configName = HOME, spaceName = "home_bottom_native") // "line_comment_native"
    /* showNative(spaceName = "block_native") /* nested */ "still_comment_native" */
    val label = "x_${listOf("inner").first()}_y"
    val raw = \"\"\"raw_${HOME}_text\"\"\"
    val url = "https://example.com/a" // after a // inside a string
}
"""
LIB_JAVA = """package com.example.lib;

class Keys {
    static final String A = "admob_id";
    static final String B = "config_show_ads";
    static final char Q = '"';
    static final String POOL = "preload_interstitial_ID1"; /* "java_comment" */
}
"""


def make_project(root: Path, **files: str | None) -> Path:
    """A mini Android Studio project on disk: Kotlin-DSL app module plus a Groovy library module.

    Keyword arguments replace a file (path with "/" written as "__"); None deletes it.
    """
    content: dict[str, str | None] = {
        "settings.gradle.kts": 'rootProject.name = "Mini"\ninclude(":app")\ninclude(":LibAds")\n// include(":old")\n',
        "app/build.gradle.kts": APP_BUILD_KTS,
        "app/src/main/AndroidManifest.xml": (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
            f'<meta-data android:name="{"com.google.android.gms.ads.APPLICATION_ID"}" '
            'android:value="@string/admob_app_id"/></application></manifest>'
        ),
        "app/src/main/res/values/strings.xml": (
            f'<resources><string name="app_name">Mini</string><string name="admob_app_id">{APP_ID}</string></resources>'
        ),
        "app/google-services.json": json.dumps(
            {
                "project_info": {"project_id": "mini-project", "project_number": "123456789012"},
                "client": [
                    {
                        "client_info": {
                            "mobilesdk_app_id": "1:2:android:other",
                            "android_client_info": {"package_name": "com.other"},
                        }
                    },
                    {
                        "client_info": {
                            "mobilesdk_app_id": "1:123456789012:android:0123456789abcdef",
                            "android_client_info": {"package_name": "com.example.mini"},
                        }
                    },
                ],
            }
        ),
        "app/src/main/assets/admob_id.txt": json.dumps(ad_data()),
        "app/src/main/java/com/example/Ads.kt": APP_KOTLIN,
        "app/src/release/java/com/example/Release.kt": 'val R = "release_only"\n',
        "app/src/debug/java/com/example/Debug.kt": 'val D = "debug_only"\n',
        "app/src/test/java/com/example/AdsTest.kt": 'val T = "test_only"\n',
        "LibAds/build.gradle": "plugins {\n    id 'com.android.library'\n}\n",
        "LibAds/src/main/java/com/example/lib/Keys.java": LIB_JAVA,
        "LibAds/src/main/assets/config_show_ads.txt": json.dumps(config_data()),
    }
    content.update({name.replace("__", "/"): text for name, text in files.items()})
    for name, text in content.items():
        path = root / name
        if text is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


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
