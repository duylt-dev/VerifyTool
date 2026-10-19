"""Opt-in 25-second session on the installed Spin Wheel app (runtime spec §1, §7)."""

import os
from pathlib import Path

import pytest

from apkverify.model import AdEvent
from apkverify.runtime.adb import find_adb, pick_device
from apkverify.runtime.log_parser import parse_line
from apkverify.runtime.session import run_session


@pytest.mark.device
@pytest.mark.skipif(not os.environ.get("APKVERIFY_TEST_SERIAL"), reason="APKVERIFY_TEST_SERIAL chưa được đặt")
def test_installed_spin_wheel_session(tmp_path: Path) -> None:
    adb = pick_device(find_adb(), os.environ["APKVERIFY_TEST_SERIAL"])
    log_path = tmp_path / "session.log"
    observed: list[AdEvent] = []
    events, started, ended = run_session(
        adb,
        Path("unused.apk"),
        "co.spinthewheel",
        install=False,
        fresh=False,
        duration=25,
        log_path=log_path,
        on_event=observed.append,
        stop_on_enter=False,
    )
    assert events == observed
    assert any(e.event == "fetch-ok" for e in events)
    assert any(e.event == "show success" for e in events)
    assert 24 <= ended - started < 40
    raw = log_path.read_text(encoding="utf-8").splitlines()
    assert events == [event for line in raw if (event := parse_line(line))]
