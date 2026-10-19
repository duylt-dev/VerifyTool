"""Name classification, window boundaries and failure recovery (runtime spec §4–§5)."""

import json

import pytest
from conftest import ad_data, config_data, make_apk_facts, make_event, make_placement, make_spec

from apkverify.model import DeviceInfo, RcValue
from apkverify.process.runtime.runtime_checks import build_runtime

DEVICE = DeviceInfo("emulator-5554", "test", "17", True)


@pytest.mark.parametrize("gap,expected", [(7.5, 5), (7.501, 0), (0.53, 6), (30, 0)])
def test_refresh_sliding_window(gap: float, expected: int) -> None:
    events = [make_event(time=1000 + i * gap) for i in range(6)]
    events.reverse()
    result = build_runtime(make_spec(), (), make_apk_facts(), DEVICE, events, 1000, 1200, "x.log")
    findings = [f for f in result.findings if f.code == "RT-FAST-REFRESH"]
    assert len(findings) == bool(expected)
    if expected:
        assert f"show {expected} lần" in findings[0].message
        assert f"{gap:.2f}s" in findings[0].message


@pytest.mark.parametrize(
    "key,value,name",
    [
        ("admob_id", json.dumps(ad_data(listAds=[dict(spaceName="rc_space", adsType="native", id="x")])), "rc_space"),
        ("config_show_ads", json.dumps(config_data(listConfig=[dict(configName="rc_config", isOn=True)])), "rc_config"),
    ],
)
def test_rc_names_are_known(key: str, value: str, name: str) -> None:
    remote = (RcValue(key, value, "rc.json"),)
    events = [make_event(names=(name,))]
    result = build_runtime(make_spec(), remote, make_apk_facts(), DEVICE, events, 0, 1, "x.log")
    assert "RT-EXTRA" not in {f.code for f in result.findings}


@pytest.mark.parametrize("structured", [False, True])
def test_extra_exact_and_structured(structured: bool) -> None:
    events = [make_event(names=("HOME_BOTTOM_NATIVE",), structured=structured)]
    remote = (RcValue("admob_id", "broken", "rc.json"), RcValue("config_show_ads", "{}", "rc.json"))
    result = build_runtime(make_spec(), remote, make_apk_facts(), DEVICE, events, 0, 1, "x.log")
    assert ("RT-EXTRA" in {f.code for f in result.findings}) == structured
    assert result.statuses[0].status == "CHƯA THẤY"


def test_failed_then_shown_and_distinct_errors() -> None:
    failures = [make_event(event=kind, code="3", message="No fill.") for kind in ("load failed", "show failed")]
    result = build_runtime(make_spec(), (), make_apk_facts(), DEVICE, failures * 2, 0, 1, "x.log")
    assert result.statuses[0].errors == ("3 No fill.",)
    assert [f.code for f in result.findings] == ["RT-SHOW-FAILED", "RT-LOAD-FAILED"]
    result = build_runtime(make_spec(), (), make_apk_facts(), DEVICE, [*failures, make_event()], 0, 1, "x.log")
    assert result.findings == ()


def test_config_only_failure_and_unit_not_found_survives_show() -> None:
    spec = make_spec(make_placement(row=5, ad_id="", config_name="spin_start", space_name=""))
    event = make_event(event="show failed", names=("spin_start", "home_bottom_native"), code="0", message="error")
    result = build_runtime(spec, (), make_apk_facts(), DEVICE, [event], 0, 1, "x.log")
    assert result.statuses[0].status == result.statuses[0].verdict == "LỖI"
    assert any(f.code == "RT-SHOW-FAILED" and f.rows == (5,) for f in result.findings)
    events = [make_event(event="show failed", code="101", message="ad unit not found"), make_event()]
    result = build_runtime(make_spec(), (), make_apk_facts(), DEVICE, events, 0, 1, "x.log")
    assert [f.code for f in result.findings] == ["RT-UNIT-NOT-FOUND"]


def test_unit_not_found_without_structured_names() -> None:
    event = make_event(
        event="show failed",
        names=("home_bottom_native",),
        structured=False,
        code="101",
        message="ad unit not found",
        ad_unit="",
    )
    result = build_runtime(make_spec(), (), make_apk_facts(), DEVICE, [event], 0, 1, "x.log")
    assert result.findings[0].rows == (5,)
    assert "(config 'home_bottom')" in result.findings[0].message
