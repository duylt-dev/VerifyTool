"""Real Android project files → ApkFacts (static-check-spec §5.1)."""

import json
from pathlib import Path

import pytest
from conftest import APP_ID, ad_data, config_data, make_project

from apkverify.errors import InputError
from apkverify.input.project_reader import find_project, read_last_inputs, read_project
from apkverify.model import FallbackAsset, ProjectInfo


def test_reads_project(tmp_path: Path) -> None:
    root = make_project(tmp_path / "Mini")
    facts = read_project(root)
    assert (facts.file_name, facts.sha256, facts.size) == ("Mini", "", 0)
    assert (facts.package, facts.version_name, facts.version_code) == ("com.example.mini", "1.0-mini", "7")
    assert facts.admob_app_id == APP_ID
    assert (facts.firebase_project_id, facts.firebase_app_id, facts.firebase_sender_id) == (
        "mini-project",
        "1:123456789012:android:0123456789abcdef",
        "123456789012",
    )
    assert facts.project == ProjectInfo(str(root), ":app", "com.github.piontech96:Dolphin-Ads:1.0.4-alpha37-1", 3, ())
    assert facts.fallbacks == (
        FallbackAsset("admob_id", True, json.dumps(ad_data()), "app/src/main/assets/admob_id.txt"),
        FallbackAsset("pangle_id", False, "", "app/src/main/assets/pangle_id.txt"),
        FallbackAsset("gam_id", False, "", "app/src/main/assets/gam_id.txt"),
        FallbackAsset("config_show_ads", True, json.dumps(config_data()), "LibAds/src/main/assets/config_show_ads.txt"),
    )
    expected = {
        "home_bottom",
        "home_bottom_native",
        "x_",
        "inner",
        "_y",
        "raw_",
        "_text",
        "https://example.com/a",
        "release_only",
        "admob_id",
        "config_show_ads",
        "preload_interstitial_ID1",
    }
    assert expected <= facts.dex_strings
    excluded = {"line_comment_native", "block_native", "still_comment_native", "java_comment"}
    assert not (excluded | {"debug_only", "test_only"}) & facts.dex_strings
    assert facts.label == "project" and facts.known("package") and facts.known("admob_app_id")


def test_find_project_walks_up(tmp_path: Path) -> None:
    root = make_project(tmp_path / "Mini")
    assert find_project(root / "app/src/main") == root.resolve()
    with pytest.raises(InputError, match="Không thấy project Android"):
        find_project(tmp_path)


def test_groovy_build_and_version_catalog(tmp_path: Path) -> None:
    build = "apply plugin: 'com.android.application'\nandroid {\n    defaultConfig {\n"
    build += "        applicationId 'com.example.groovy'\n        versionCode 3\n        versionName '2.0'\n    }\n}\n"
    root = make_project(
        tmp_path / "Mini",
        **{
            "settings.gradle.kts": None,
            "settings.gradle": "include ':app', ':LibAds'\n",
            "app/build.gradle.kts": None,
            "app/build.gradle": build,
            "gradle/libs.versions.toml": '# ads = "com.github.piontech96:Dolphin-Ads:0.1"\n'
            'ads = { module = "com.github.piontech96:Dolphin-Ads", version.ref = "ads" }\n',
        },
    )
    facts = read_project(root)
    assert (facts.package, facts.version_name, facts.version_code) == ("com.example.groovy", "2.0", "3")
    assert facts.project.ad_library == "com.github.piontech96:Dolphin-Ads"
    assert facts.firebase_app_id is None


def test_unresolved_values(tmp_path: Path) -> None:
    build = 'plugins { id("com.android.application") }\nandroid {\n    defaultConfig {\n'
    build += "        applicationId = libs.versions.appId.get()\n        versionName = computeName()\n    }\n}\n"
    manifest = (
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
        '<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="${admobAppId}"/>'
        "</application></manifest>"
    )
    root = make_project(
        tmp_path / "Mini",
        **{
            "app/build.gradle.kts": build,
            "app/src/main/AndroidManifest.xml": manifest,
            "app/google-services.json": None,
        },
    )
    facts = read_project(root)
    assert (facts.package, facts.version_name, facts.version_code, facts.admob_app_id) == ("", "", "", "${admobAppId}")
    assert facts.project.unresolved == (("package", "libs.versions.appId.get()"), ("admob_app_id", "${admobAppId}"))
    assert facts.project.ad_library == ""
    assert not facts.known("package") and not facts.known("admob_app_id")


def test_missing_values(tmp_path: Path) -> None:
    manifest = '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application/></manifest>'
    build = "plugins { alias(libs.plugins.android.application) }\n"
    strings = '<resources><string name="admob_app_id">x</string></resources>'
    root = make_project(
        tmp_path / "Mini",
        **{
            "app/build.gradle.kts": build,
            "app/src/main/AndroidManifest.xml": manifest,
            "app/src/main/res/values/strings.xml": strings,
        },
    )
    facts = read_project(root)
    assert facts.admob_app_id is None
    assert facts.project.unresolved == (("package", "không có dòng applicationId trong app/build.gradle.kts"),)


def test_unknown_string_resource_stays_a_reference(tmp_path: Path) -> None:
    root = make_project(tmp_path / "Mini", **{"app/src/main/res/values/strings.xml": "<resources/>"})
    facts = read_project(root)
    assert facts.admob_app_id == "@string/admob_app_id"
    assert facts.project.unresolved == (("admob_app_id", "@string/admob_app_id"),)


def test_no_application_module(tmp_path: Path) -> None:
    root = make_project(tmp_path / "Mini", **{"app/build.gradle.kts": "plugins { id 'com.android.library' }\n"})
    with pytest.raises(InputError, match="Không thấy module ứng dụng"):
        read_project(root)


def test_invalid_manifest(tmp_path: Path) -> None:
    root = make_project(tmp_path / "Mini", **{"app/src/main/AndroidManifest.xml": "<manifest"})
    with pytest.raises(InputError, match="File XML không hợp lệ"):
        read_project(root)


def test_read_last_inputs(tmp_path: Path) -> None:
    assert read_last_inputs(tmp_path) == {}
    existing = tmp_path / "admob_id.json"
    existing.write_text("{}", encoding="utf-8")
    data = {"admob_id": str(existing), "spec": str(tmp_path / "gone.xlsx")}
    (tmp_path / "last-inputs.json").write_text(json.dumps(data), encoding="utf-8")
    assert read_last_inputs(tmp_path) == {"admob_id": existing}
    (tmp_path / "last-inputs.json").write_text("[1, 2]", encoding="utf-8")
    assert read_last_inputs(tmp_path) == {}


MANIFEST_WITH = (
    '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
    '<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="{}"/></application></manifest>'
)


def test_app_id_declared_only_in_a_flavor_is_unresolved(tmp_path: Path) -> None:
    no_meta = '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application/></manifest>'
    root = make_project(
        tmp_path / "Mini",
        **{
            "app/src/main/AndroidManifest.xml": no_meta,
            "app/src/free/AndroidManifest.xml": MANIFEST_WITH.format(APP_ID),
        },
    )
    facts = read_project(root)
    assert facts.admob_app_id == APP_ID
    assert facts.project.unresolved == (
        ("admob_app_id", f"{APP_ID} chỉ khai báo trong app/src/free/AndroidManifest.xml"),
    )


def test_app_id_string_that_differs_between_source_sets_is_unresolved(tmp_path: Path) -> None:
    other = '<resources><string name="admob_app_id">ca-app-pub-1111111111111111~9999999999</string></resources>'
    root = make_project(tmp_path / "Mini", **{"app/src/free/res/values/strings.xml": other})
    facts = read_project(root)
    assert facts.admob_app_id == APP_ID
    assert facts.project.unresolved == (("admob_app_id", "@string/admob_app_id khác nhau giữa các source set"),)


def test_multiplatform_test_source_sets_are_skipped(tmp_path: Path) -> None:
    root = make_project(
        tmp_path / "Mini",
        **{
            "app/src/commonTest/kotlin/A.kt": 'val a = "kmp_test_only"\n',
            "app/src/androidUnitTest/kotlin/B.kt": 'val b = "unit_test_only"\n',
        },
    )
    assert not {"kmp_test_only", "unit_test_only"} & read_project(root).dex_strings


def test_malformed_google_services_is_only_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    root = make_project(tmp_path / "Mini", **{"app/google-services.json": '{"client": 5}'})
    facts = read_project(root)
    assert (facts.firebase_project_id, facts.firebase_app_id, facts.firebase_sender_id) == (None, None, None)
    assert "google-services.json không đọc được" in caplog.text
