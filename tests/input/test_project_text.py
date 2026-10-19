"""Pure readers of Gradle, manifest, resource and google-services text (static-check-spec §5.1)."""

import json

import pytest

from apkverify.input.project_text import (
    ad_library,
    application_id,
    firebase_ids,
    gradle_value,
    included_modules,
    is_application,
    manifest_app_id,
    string_resources,
)


@pytest.mark.parametrize(
    "settings,expected",
    [
        ('include(":app")\ninclude(":LibAds")', [":app", ":LibAds"]),
        ("include ':app', ':lib'", [":app", ":lib"]),
        ('include(":a", ":b:c")\ninclude(":a")', [":a", ":b:c"]),
        ('includeBuild("../plugins")\ninclude("app")', [":app"]),
        ('dependencyResolutionManagement { includeGroupByRegex("com\\\\.android.*") }', []),
        ('include(\n    ":app",\n    ":ads",\n)', [":app", ":ads"]),
        ("include ':app',\n        ':core'\nrootProject.name = 'x'", [":app", ":core"]),
    ],
)
def test_included_modules(settings: str, expected: list[str]) -> None:
    assert included_modules(settings) == expected


@pytest.mark.parametrize(
    "build,expected",
    [
        ("plugins { alias(libs.plugins.android.application) }", True),
        ('plugins { id("com.android.application") }', True),
        ("apply plugin: 'com.android.application'", True),
        ("plugins { alias(libs.plugins.android.library) }", False),
        ("plugins { id 'com.android.library' }", False),
    ],
)
def test_is_application(build: str, expected: bool) -> None:
    assert is_application(build) is expected


@pytest.mark.parametrize(
    "build,name,expected",
    [
        ('    applicationId = "co.app"', "applicationId", ("co.app", '"co.app"')),
        ("    applicationId 'co.app'", "applicationId", ("co.app", "'co.app'")),
        ('    applicationIdSuffix = ".dev"\n    applicationId = "co.app"', "applicationId", ("co.app", '"co.app"')),
        ("    versionCode = 18", "versionCode", ("18", "18")),
        ("    versionCode 18 ", "versionCode", ("18", "18")),
        ("    applicationId = libs.versions.appId.get()", "applicationId", (None, "libs.versions.appId.get()")),
        ('    versionName = "1.$minor"', "versionName", (None, '"1.$minor"')),
        ('    base.archivesName.set("A_$versionName")', "versionName", (None, "")),
        ('    namespace = "co.ns"', "applicationId", (None, "")),
    ],
)
def test_gradle_value(build: str, name: str, expected: tuple[str | None, str]) -> None:
    assert gradle_value(build, name) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        (
            'implementation("com.github.piontech96:Dolphin-Ads:1.0.4-alpha37-1")',
            "com.github.piontech96:Dolphin-Ads:1.0.4-alpha37-1",
        ),
        ("implementation 'com.github.piontech96:Dolphin-Ads:1.0'", "com.github.piontech96:Dolphin-Ads:1.0"),
        (
            'dolphin = { module = "com.github.piontech96:Dolphin-Ads", version.ref = "ads" }',
            "com.github.piontech96:Dolphin-Ads",
        ),
        (
            'dolphin = { group = "com.github.piontech96", name = "Dolphin-Ads", version = "1" }',
            "com.github.piontech96:Dolphin-Ads",
        ),
        ('implementation("com.github.piontech96:Dolphin-Ads-Extra:1.0")', ""),
        ('implementation(project(":LibAds"))', ""),
    ],
)
def test_ad_library(text: str, expected: str) -> None:
    assert ad_library(text) == expected


def test_ad_library_map_forms() -> None:
    groovy = "implementation group: 'com.github.piontech96', name: 'Dolphin-Ads', version: '1.0.4'"
    toml = 'ads = { name = "Dolphin-Ads", group = "com.github.piontech96", version.ref = "ads" }'
    assert ad_library(groovy) == ad_library(toml) == "com.github.piontech96:Dolphin-Ads"


DEFAULT = '    defaultConfig {\n        applicationId = "com.x"\n    }\n'


def nested(outer: str, header: str, line: str) -> str:
    return DEFAULT + f"    {outer} {{\n        {header} {{\n            {line}\n        }}\n    }}\n"


@pytest.mark.parametrize(
    "build,expected",
    [
        (DEFAULT, ("com.x", '"com.x"')),
        (nested("productFlavors", "appRelease", 'applicationId "com.x"'), ("com.x", '"com.x"')),
        (
            nested("productFlavors", 'create("free")', 'applicationId = "com.y"'),
            (None, "applicationId khác nhau theo flavor: com.x, com.y"),
        ),
        (nested("buildTypes", 'getByName("debug")', 'applicationIdSuffix = ".debug"'), ("com.x", '"com.x"')),
        (
            nested("productFlavors", 'create("free")', 'applicationIdSuffix = ".free"'),
            (None, 'applicationIdSuffix ".free" trong create("free")'),
        ),
        ("    applicationId = libs.versions.id.get()\n", (None, "libs.versions.id.get()")),
        ('    namespace = "com.ns"\n', (None, "")),
    ],
)
def test_application_id(build: str, expected: tuple[str | None, str]) -> None:
    assert application_id(build) == expected


MANIFEST = (
    '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>{}</application></manifest>'
)


@pytest.mark.parametrize(
    "body,expected",
    [
        (
            '<meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="@string/admob"/>',
            "@string/admob",
        ),
        ('<meta-data android:name="other" android:value="x"/>', None),
        ("", None),
    ],
)
def test_manifest_app_id(body: str, expected: str | None) -> None:
    assert manifest_app_id(MANIFEST.format(body)) == expected


def test_string_resources() -> None:
    xml = (
        '<resources><string name="a">plain</string><string name="b">"quoted"</string>'
        '<string name="c">it\\\'s</string></resources>'
    )
    assert string_resources(xml) == {"a": "plain", "b": "quoted", "c": "it's"}


def test_firebase_ids_match_the_package_client() -> None:
    data = {
        "project_info": {"project_id": "p", "project_number": "42"},
        "client": [
            {"client_info": {"mobilesdk_app_id": "1:42:android:a", "android_client_info": {"package_name": "co.a"}}},
            {"client_info": {"mobilesdk_app_id": "1:42:android:b", "android_client_info": {"package_name": "co.b"}}},
        ],
    }
    assert firebase_ids(json.dumps(data), "co.b") == ("p", "1:42:android:b", "42")
    assert firebase_ids(json.dumps(data), "co.c") == ("p", None, "42")
