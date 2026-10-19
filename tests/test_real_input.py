"""Acceptance contract: static-check-spec §9, measured inputs 2026-10-05."""

from collections import Counter

import pytest
from conftest import ROOT

from apkverify.apk_reader import read_apk
from apkverify.checks.static_result import build
from apkverify.formats import publisher
from apkverify.inputs import discover
from apkverify.model import Severity
from apkverify.rc_reader import parse_ad_unit_list, read_rc_files
from apkverify.spec_reader import read_spec


@pytest.mark.real_input
def test_spin_wheel_acceptance() -> None:
    inputs = discover(ROOT / "input")
    spec, apk, remote = read_spec(inputs.spec), read_apk(inputs.apk), read_rc_files(inputs.rc_files)
    placements = spec.placements
    assert len(placements) == 48
    assert Counter(p.format for p in placements) == {
        "Native": 22,
        "Interstitial": 13,
        "Native Full Screen": 6,
        "Banner Adapt": 4,
        "Open Ad": 3,
    }
    ids = [p.ad_id for p in placements if p.has_id]
    assert len(ids) == len(set(ids)) == 38
    assert len({publisher(ad_id) for ad_id in ids}) == 1
    assert len({p.config_name for p in placements if p.has_config}) == 34
    assert sum(p.has_config and not p.has_id for p in placements) == 10
    assert sum(p.has_id and not p.has_config for p in placements) == 2
    assert (apk.package, apk.version_name, apk.version_code) == ("co.spinthewheel", "dev_1.0.1", "2")
    assert apk.admob_app_id == "ca-app-pub-2222869408518511~3967138465"
    assert apk.firebase_project_id == "spin-wheel-2-3b442"
    admob = parse_ad_unit_list("admob_id", next(v.value for v in remote if v.key == "admob_id"))
    assert admob.app_id == apk.admob_app_id
    assets = {a.key: a for a in apk.fallbacks}
    for key in ("admob_id", "config_show_ads"):
        assert assets[key].present and assets[key].text == ""
    result = build(spec, remote, apk)
    assert Counter(f.code for f in result.findings) == {
        "APK-SPACE-MISSING": 1,
        "RC-CONFIG-OFF": 16,
        "APK-FALLBACK-EMPTY": 2,
        "SPEC-NAME-MISMATCH": 6,
    }
    assert Counter(f.severity for f in result.findings) == {Severity.ERROR: 1, Severity.WARN: 18, Severity.INFO: 6}
    missing = next(f for f in result.findings if f.code == "APK-SPACE-MISSING")
    assert missing.rows == (20,)
    assert missing.message == (
        "Code không gọi Ad Space 'splash_interstitial' (dòng 20): ID ca-app-pub-2222869408518511/1597407259 "
        "sẽ không bao giờ được request."
    )
    off_names = {
        "language2.1",
        "language2.2",
        "Splash_afterinter",
        "Onboard2",
        "onboard3",
        "afterinterstitial",
        "onboard3-start",
        "template_between",
        "template_cate",
        "my_spin_between",
        "my_spin_again",
        "template_content",
        "spin_start",
        "spin_edit",
        "spin_middle",
        "customize_save",
    }
    assert {f.message for f in result.findings if f.code == "RC-CONFIG-OFF"} == {
        f"Vị trí '{name}' đang TẮT (isOn=false): sẽ không show." for name in off_names
    }
    assert [f.rows for f in result.findings if f.code == "SPEC-NAME-MISMATCH"] == [(6,), (7,), (8,), (9,), (21,), (34,)]
    assert not result.passed and len(result.statuses) == 48
