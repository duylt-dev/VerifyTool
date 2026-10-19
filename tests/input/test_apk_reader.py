"""APK reader against the real aapt2/d8 fixture (static-check-spec §5)."""

import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest
from conftest import APP_ID, MINI_APK, UNIT_ID

from apkverify.errors import ApkError
from apkverify.input.apk_reader import read_apk
from apkverify.process.rc_parse import parse_ad_unit_list


def test_mini_apk_facts() -> None:
    facts = read_apk(MINI_APK)
    assert (facts.file_name, facts.package, facts.version_name, facts.version_code) == (
        "mini.apk",
        "com.example.mini",
        "1.0-mini",
        "7",
    )
    assert facts.admob_app_id == APP_ID
    assert (facts.firebase_project_id, facts.firebase_app_id, facts.firebase_sender_id) == (
        "mini-project",
        "1:123456789012:android:0123456789abcdef",
        "123456789012",
    )
    assert facts.size == MINI_APK.stat().st_size
    assert facts.sha256 == hashlib.sha256(MINI_APK.read_bytes()).hexdigest()
    assets = {a.key: a for a in facts.fallbacks}
    assert assets["admob_id"].present
    units = parse_ad_unit_list("admob_id", assets["admob_id"].text)
    assert units.app_id == APP_ID and units.package == "com.example.mini"
    assert units.units[0].ad_id == UNIT_ID
    assert assets["config_show_ads"].present and assets["config_show_ads"].text == ""
    assert not assets["gam_id"].present and assets["gam_id"].text == ""
    assert not assets["pangle_id"].present and assets["pangle_id"].text == ""
    assert {"admob_id", "config_show_ads", "home_bottom", "home_bottom_native", "Định dạng"} <= facts.dex_strings
    assert "splash_interstitial" not in facts.dex_strings


def test_root_multidex_and_fallback_bom(tmp_path: Path) -> None:
    path = tmp_path / "multiple.apk"
    with ZipFile(MINI_APK) as source, ZipFile(path, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr("classes2.dex", source.read("classes.dex"))
        target.writestr("assets/ignored.dex", b"invalid dex ignored")
        target.writestr("directory/classes3.dex", b"invalid dex ignored")
        target.writestr("assets/gam_id.txt", b"\xef\xbb\xbftext\xff")
    facts = read_apk(path)
    assert facts.dex_strings == read_apk(MINI_APK).dex_strings
    assert next(a.text for a in facts.fallbacks if a.key == "gam_id") == "text�"


@pytest.mark.parametrize("kind", ["missing", "invalid_zip", "invalid_dex", "invalid_manifest"])
def test_unreadable_apk(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "broken.apk"
    if kind == "invalid_zip":
        path.write_bytes(b"not an apk")
    elif kind == "invalid_manifest":
        with ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"not binary XML")
    elif kind == "invalid_dex":
        with ZipFile(MINI_APK) as source, ZipFile(path, "w") as target:
            for name in source.namelist():
                target.writestr(name, b"not dex" if name == "classes.dex" else source.read(name))
    with pytest.raises(ApkError) as error:
        read_apk(path)
    assert str(error.value).startswith("Không đọc được APK broken.apk: ")
    assert str(error.value).endswith(".")
