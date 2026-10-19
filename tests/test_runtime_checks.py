"""Every runtime finding has a positive and negative case (runtime-check-spec §5)."""

import json

import pytest
from conftest import UNIT_ID, config_data, make_apk_facts, make_event, make_placement, make_spec

from apkverify.model import AdEvent, DeviceInfo, RcValue, RuntimeResult, Severity
from apkverify.runtime.runtime_checks import build_runtime

DEVICE = DeviceInfo("emulator-5554", "test", "17", True)


def result_for(events: list[AdEvent], remote: tuple[RcValue, ...] = ()) -> RuntimeResult:
    return build_runtime(make_spec(), remote, make_apk_facts(), DEVICE, events, 1000, 1100, "session.log")


@pytest.mark.parametrize(
    "code,severity,events,message,rows",
    [
        (
            "RT-RC-FETCH-FAILED",
            Severity.ERROR,
            [make_event(event="fetch-failed", names=(), structured=False)],
            "Fetch Remote Config lỗi: thư viện không đọc danh sách ID nên không quảng cáo nào có ID.",
            (),
        ),
        (
            "RT-UNIT-NOT-FOUND",
            Severity.ERROR,
            [make_event(event="show failed", code="101", message="ad unit not found")],
            "Thiếu ID lúc chạy: 'home_bottom_native' (config 'home_bottom') không có trong danh sách ad unit.",
            (5,),
        ),
        (
            "RT-SHOW-FAILED",
            Severity.ERROR,
            [make_event(event="show failed", code="0", message="Internal error")],
            "'home_bottom_native' show lỗi: 0 Internal error.",
            (5,),
        ),
        (
            "RT-LOAD-FAILED",
            Severity.WARN,
            [make_event(event="load failed", code="3", message="No fill.")],
            "'home_bottom_native' load lỗi: 3 No fill.",
            (5,),
        ),
        (
            "RT-LOADED-NOT-SHOWN",
            Severity.WARN,
            [make_event(event="load success")],
            "'home_bottom_native' đã load nhưng chưa show.",
            (5,),
        ),
        (
            "RT-NOT-SEEN",
            Severity.WARN,
            [make_event(event="start load", names=("other",), structured=False)],
            "Chưa thấy 'home_bottom_native' (dòng 5): chưa đi tới màn này, hoặc vị trí không được gọi.",
            (5,),
        ),
        (
            "RT-NO-EVENTS",
            Severity.ERROR,
            [make_event(event="screen", names=(), structured=False)],
            "Không thấy sự kiện quảng cáo nào trong phiên: app không chạy tới quảng cáo, hoặc bản build không "
            "ghi log TESTERADSEVENT. Phiên này không đủ để kết luận.",
            (),
        ),
        (
            "RT-EXTRA",
            Severity.WARN,
            [make_event(names=("unexpected",))],
            "Thừa lúc chạy: 'unexpected' có trong log nhưng không có trong spec.",
            (),
        ),
        (
            "RT-FAST-REFRESH",
            Severity.WARN,
            [make_event(time=1000 + i) for i in range(5)],
            "'home_bottom_native' show 5 lần trong 30 giây (khoảng cách ngắn nhất 1.00s): kiểm tra logic reload; "
            "AdMob khuyến nghị không refresh nhanh hơn 30 giây.",
            (5,),
        ),
    ],
)
def test_finding_contract(
    code: str,
    severity: Severity,
    events: list[AdEvent],
    message: str,
    rows: tuple[int, ...],
) -> None:
    result = result_for(events)
    findings = [f for f in result.findings if f.code == code]
    assert len(findings) == 1
    assert (findings[0].severity, findings[0].message, findings[0].rows) == (severity, message, rows)
    assert code not in {f.code for f in result_for([make_event()]).findings}
    assert result.passed == (severity != Severity.ERROR)


@pytest.mark.parametrize(
    "shown,source,actual,wrong",
    [
        (False, "Interstitial Preload", "pool", True),
        (True, "Interstitial Preload", "pool", False),
        (False, "open_app", "pool", False),
        (False, "Interstitial Preload", "sibling", False),
    ],
)
def test_wrong_space(shown: bool, source: str, actual: str, wrong: bool) -> None:
    spec = make_spec(
        make_placement(row=20, config_name="splash", space_name="expected", format="Interstitial"),
        make_placement(row=21, config_name="splash", space_name="sibling", format="Interstitial"),
        make_placement(row=22, config_name="splash", space_name="splash_openad", format="Open Ad"),
        make_placement(row=23, config_name="", space_name="pool", format="Interstitial"),
    )
    events = [make_event(source=source, names=("splash", actual))]
    if shown:
        events.append(make_event(names=("expected",)))
    result = build_runtime(spec, (), make_apk_facts(), DEVICE, events, 0, 1, "session.log")
    findings = [f for f in result.findings if f.code == "RT-WRONG-SPACE" and f.rows == (20,)]
    assert bool(findings) == wrong
    if wrong:
        assert findings[0].message == (
            f"'splash' (dòng 20) show bằng Ad Space 'pool' thay vì 'expected': ID {UNIT_ID} không được dùng."
        )
        assert findings[0].severity == Severity.ERROR
        assert all(f.rows != (22,) for f in result.findings if f.code == "RT-WRONG-SPACE")


@pytest.mark.parametrize(
    "kinds,status",
    [
        ([], "CHƯA THẤY"),
        (["start load"], "ĐÃ REQUEST"),
        (["show failed"], "LỖI"),
        (["load failed"], "LỖI"),
        (["load success"], "ĐÃ LOAD"),
        (["load failed", "show success"], "ĐÃ SHOW"),
        (["load success", "show failed"], "ĐÃ LOAD"),
    ],
)
def test_status_precedence(kinds: list[str], status: str) -> None:
    result = result_for([make_event(event=kind, time=1000 + i) for i, kind in enumerate(kinds)])
    row = result.statuses[0]
    assert row.status == status
    assert row.shows == kinds.count("show success")
    assert row.first_time == (1000 if kinds else None)
    assert row.last_time == (999 + len(kinds) if kinds else None)
    # A row's verdict comes from the findings that name its row, not from session-wide ones such as RT-NO-EVENTS.
    severities = {f.severity for f in result.findings if row.placement.row in f.rows}
    expected = "LỖI" if Severity.ERROR in severities else "CẢNH BÁO" if Severity.WARN in severities else "ĐẠT"
    assert row.verdict == expected


def test_not_seen_off_and_per_row() -> None:
    remote = (
        RcValue(
            "config_show_ads",
            json.dumps(
                config_data(
                    listConfig=[
                        dict(configName="home_bottom", isOn=False, type="native"),
                    ]
                )
            ),
            "config.json",
        ),
    )
    finding = next(f for f in result_for([], remote).findings if f.code == "RT-NOT-SEEN")
    assert finding.message == (
        "Chưa thấy 'home_bottom_native' (dòng 5) — đang TẮT trên Remote Config: "
        "chưa đi tới màn này, hoặc vị trí không được gọi."
    )
    spec = make_spec(make_placement(row=5), make_placement(row=6))
    result = build_runtime(spec, (), make_apk_facts(), DEVICE, [], 0, 1, "session.log")
    assert [f.rows for f in result.findings if f.code == "RT-NOT-SEEN"] == [(5,), (6,)]
