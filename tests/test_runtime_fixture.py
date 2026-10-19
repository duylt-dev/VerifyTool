"""Real emulator recording acceptance (runtime-check-spec §7)."""

import pytest
from conftest import ROOT, make_apk_facts, make_placement, make_spec

from apkverify.apk_reader import read_apk
from apkverify.inputs import discover
from apkverify.model import AdEvent, DeviceInfo, RuntimeResult
from apkverify.rc_reader import read_rc_files
from apkverify.runtime.log_parser import parse_line
from apkverify.runtime.runtime_checks import build_runtime
from apkverify.spec_reader import read_spec

DEVICE = DeviceInfo("emulator-5554", "sdk_gphone16k_arm64", "17", True)


def recorded_events() -> list[AdEvent]:
    lines = (ROOT / "tests/fixtures/logcat_spinwheel2_session1.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 391
    assert sum(line.endswith("TESTERADSEVENT: ") for line in lines) == 40
    return [event for line in lines if (event := parse_line(line))]


def assert_fixture_findings(result: RuntimeResult) -> None:
    wrong = [f for f in result.findings if f.code == "RT-WRONG-SPACE"]
    assert len(wrong) == 1
    assert wrong[0].rows == (20,)
    assert "Ad Space 'preload_Interstitial_ID1'" in wrong[0].message
    fast = [f for f in result.findings if f.code == "RT-FAST-REFRESH" and "home_bottom_native" in f.message]
    assert len(fast) == 1
    assert int(fast[0].message.split(" show ")[1].split()[0]) >= 5
    assert "0.53s" in fast[0].message
    statuses = {s.placement.space_name or s.placement.config_name: s for s in result.statuses}
    assert statuses["Language1.1_native1"].status == "ĐÃ SHOW"
    assert statuses["Language1.1_native2"].status == "ĐÃ LOAD"
    assert statuses["spin_start"].status == "CHƯA THẤY"
    assert statuses["home_bottom_native"].shows == 90
    assert "RT-RC-FETCH-FAILED" not in {f.code for f in result.findings}


def test_recorded_session() -> None:
    rows = [
        (20, "splash", "splash_interstitial", "Interstitial"),
        (21, "splash", "splash_openad", "Open Ad"),
        (37, "", "preload_Interstitial_ID1", "Interstitial"),
        (40, "home_bottom", "home_bottom_native", "Native"),
        (41, "home_bottom", "home_bottom_adaptive", "Banner Adapt"),
        (6, "Language1.1", "Language1.1_native1", "Native"),
        (7, "Language1.1", "Language1.1_native2", "Native"),
    ]
    placements = [
        make_placement(row=row, config_name=config, space_name=space, format=fmt) for row, config, space, fmt in rows
    ]
    placements.append(make_placement(row=50, config_name="spin_start", space_name="", ad_id=""))
    events = recorded_events()
    assert sum(e.event == "screen" for e in events) == 4
    assert not any("failed" in e.event for e in events)
    shows = [e.time for e in events if e.event == "show success" and "home_bottom_native" in e.names]
    # Measured on the whole fixture 2026-10-05: 90 shows over 89.8 s (runtime-check-spec §7).
    assert len(shows) == 90
    assert shows[-1] - shows[0] == pytest.approx(89.8, abs=0.1)
    assert not any("splash_interstitial" in e.names for e in events)
    result = build_runtime(
        make_spec(*placements), (), make_apk_facts(), DEVICE, events, events[0].time, events[-1].time, "session.log"
    )
    assert_fixture_findings(result)


@pytest.mark.real_input
def test_real_spec_rc_recorded_session() -> None:
    inputs = discover(ROOT / "input")
    events = recorded_events()
    result = build_runtime(
        read_spec(inputs.spec),
        read_rc_files(inputs.rc_files),
        read_apk(inputs.apk),
        DEVICE,
        events,
        events[0].time,
        events[-1].time,
        "session.log",
    )
    assert_fixture_findings(result)
