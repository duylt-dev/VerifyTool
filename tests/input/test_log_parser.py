"""Real log shapes and missing failure shapes (runtime-check-spec §3–§4)."""

import pytest
from conftest import ROOT, UNIT_ID

from apkverify.input.device.log_parser import parse_line

LOG = ROOT / "tests/fixtures/logcat_spinwheel2_session1.txt"


@pytest.mark.parametrize(
    "event,source,names,unit",
    [
        ("start load", "AdmobNativeAd", ("Language1.1", "Language1.1_native1"), "1266234769"),
        ("start load", "Interstitial", ("preload_Interstitial_ID1",), "5397051460"),
        ("load success", "AdmobNativeAd", ("Language1.2", "Language1.2_native1"), "4163860841"),
        ("load success", "Interstitial Preload", ("preload_Interstitial_ID1",), "5397051460"),
        ("start load", "AdmobNativeInterstitialAd", ("Splash_afterinter", "Splash_afterinter_native"), "2910488928"),
        ("load success", "AdmobNativeInterstitialAd", ("Splash_afterinter", "Splash_afterinter_native"), "2910488928"),
        ("onAdsExhausted", "Interstitial Preload", ("preload_Interstitial_ID1",), "5397051460"),
        ("show success", "Interstitial Preload", ("splash", "preload_Interstitial_ID1"), "5397051460"),
        ("show success", "native_interstitial", ("Splash_afterinter", "Splash_afterinter_native"), "2910488928"),
        ("close", "Interstitial Preload", ("splash", "preload_Interstitial_ID1"), "5397051460"),
        ("close", "native_interstitial", ("Splash_afterinter", "Splash_afterinter_native"), "2910488928"),
        ("show success", "native", ("Language1.1", "Language1.1_native1"), "1266234769"),
        ("start load", "AdmobOpenAppAd", ("appresume", "appresume_openad1"), "6654292812"),
        ("load success", "AdmobOpenAppAd", ("appresume", "appresume_openad1"), "6654292812"),
    ],
)
def test_real_shape(event: str, source: str, names: tuple[str, ...], unit: str) -> None:
    line = next(line for line in LOG.read_text(encoding="utf-8").splitlines() if f": {event} {source}: " in line)
    parsed = parse_line(line)
    assert parsed is not None
    assert (parsed.event, parsed.source, parsed.names, parsed.ad_unit, parsed.structured) == (
        event,
        source,
        names,
        f"ca-app-pub-2222869408518511/{unit}",
        True,
    )
    assert parsed.code == parsed.message == ""


def test_real_screen_and_fetch() -> None:
    events = [e for line in LOG.read_text(encoding="utf-8").splitlines() if (e := parse_line(line))]
    screen = next(e for e in events if e.event == "screen")
    assert (screen.source, screen.names, screen.ad_unit, screen.structured) == (
        "co.spinthewheel:id/splashFragment",
        (),
        "",
        False,
    )
    fetch = next(e for e in events if e.event == "fetch-ok")
    assert (fetch.source, fetch.names, fetch.ad_unit, fetch.structured) == ("", (), "", False)
    assert screen.time == 1791192282.018
    assert sum(e.event == "screen" for e in events) == 4


@pytest.mark.parametrize(
    "message,event,source,names,code,error,structured",
    [
        (
            f"load failed AdmobNativeAd: c s {UNIT_ID} 3 No fill.",
            "load failed",
            "AdmobNativeAd",
            ("c", "s"),
            "3",
            "No fill.",
            True,
        ),
        (
            f"show failed native: c s {UNIT_ID} 0 Internal error",
            "show failed",
            "native",
            ("c", "s"),
            "0",
            "Internal error",
            True,
        ),
        (
            "show failed splash_interstitial: 101 ad unit not found",
            "show failed",
            "splash_interstitial",
            ("splash_interstitial",),
            "101",
            "ad unit not found",
            False,
        ),
        (
            "show failed AdmobNativeAd: Language1.1 Activity is finishing or destroyed",
            "show failed",
            "AdmobNativeAd",
            ("Language1.1",),
            "",
            "Activity is finishing or destroyed",
            False,
        ),
        (
            f"banner refresh failed banner: c s {UNIT_ID} 3 No fill.",
            "banner refresh failed",
            "banner",
            ("c", "s"),
            "3",
            "No fill.",
            True,
        ),
        (
            f"show failed native: c s {UNIT_ID} retry 101 ad unit not found",
            "show failed",
            "native",
            ("c", "s"),
            "101",
            "ad unit not found",
            True,
        ),
    ],
)
def test_failure_shape(
    message: str,
    event: str,
    source: str,
    names: tuple[str, ...],
    code: str,
    error: str,
    structured: bool,
) -> None:
    parsed = parse_line(f" 1000.125 12 34 D TESTERADSEVENT: {message}\n")
    assert parsed is not None
    assert (
        parsed.event,
        parsed.source,
        parsed.names,
        parsed.ad_unit,
        parsed.structured,
        parsed.code,
        parsed.message,
    ) == (
        event,
        source,
        names,
        UNIT_ID if structured else "",
        structured,
        code,
        error,
    )


@pytest.mark.parametrize("event", ["clicked", "click", "got reward", "banner refresh"])
def test_other_template_events(event: str) -> None:
    parsed = parse_line(f"1000.125 12 34 D TESTERADSEVENT: {event} native: c s {UNIT_ID}")
    assert parsed is not None
    assert (parsed.event, parsed.source, parsed.names, parsed.ad_unit, parsed.structured) == (
        event,
        "native",
        ("c", "s"),
        UNIT_ID,
        True,
    )


def test_fetch_failed() -> None:
    event = parse_line("1000.125 12 34 D CHECKINITADS: initRemoteConfig: isSuccessful = false")
    assert event is not None
    assert (event.event, event.source, event.names, event.ad_unit, event.structured) == (
        "fetch-failed",
        "",
        (),
        "",
        False,
    )


@pytest.mark.parametrize(
    "line",
    [
        "",
        "--------- beginning of main",
        "1000 12 34 D TESTERADSEVENT: close x: c",
        "1000.125 12 34 D TESTERADSEVENT: ",
        "1000.125 12 34 D TESTERADSEVENT: unknown native: c",
        "1000.125 12 34 D OTHER: show success native: c",
        "1000.125 12 34 D CHECKINITADS: other",
    ],
)
def test_ignored(line: str) -> None:
    assert parse_line(line) is None
