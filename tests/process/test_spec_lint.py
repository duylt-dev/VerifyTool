"""Every SPEC finding has positive and negative evidence (§6.1)."""

import pytest
from conftest import OTHER_ID, UNIT_ID, make_placement, make_spec

from apkverify.model import Finding, Severity
from apkverify.process.static.spec_lint import lint

CASES = (
    (
        "SPEC-NO-KEY",
        [dict(ad_id="", config_name="")],
        Severity.WARN,
        (5,),
        "Dòng 5: có Định Dạng nhưng không có Config Name lẫn ID.",
    ),
    ("SPEC-ID-FORMAT", [dict(ad_id="bad")], Severity.WARN, (5,), "Dòng 5: ID 'bad' sai định dạng AdMob."),
    ("SPEC-DUP-ID", [{}, dict(row=6, space_name="other")], Severity.WARN, (5, 6), f"ID {UNIT_ID} lặp ở dòng 5, 6."),
    (
        "SPEC-DUP-SPACE",
        [{}, dict(row=6, ad_id=OTHER_ID)],
        Severity.WARN,
        (5, 6),
        "Ad Space 'home_bottom_native' lặp ở dòng 5, 6.",
    ),
    (
        "SPEC-PUBLISHER",
        [{}, dict(row=6, ad_id="ca-app-pub-2222222222222222/3333333333", space_name="other")],
        Severity.WARN,
        (),
        "Spec có ID của nhiều publisher: 1111111111111111, 2222222222222222.",
    ),
    (
        "SPEC-UNKNOWN-FORMAT",
        [dict(format="Unknown")],
        Severity.WARN,
        (5,),
        "Dòng 5: Định Dạng 'Unknown' chưa có trong bảng ánh xạ.",
    ),
    (
        "SPEC-NAME-MISMATCH",
        [dict(network_name="Am_Home_bottom_native")],
        Severity.INFO,
        (5,),
        "Dòng 5: Ad Space 'home_bottom_native' khác Network Ad Name 'Am_Home_bottom_native' (ngoài tiền tố Am_).",
    ),
)


@pytest.mark.parametrize("code,changes,severity,rows,message", CASES)
def test_finding(code: str, changes: list[dict], severity: Severity, rows: tuple[int, ...], message: str) -> None:
    spec = make_spec(*(make_placement(**change) for change in changes))
    assert [f for f in lint(spec) if f.code == code] == [Finding(code, severity, message, rows)]


@pytest.mark.parametrize("code", [case[0] for case in CASES])
def test_absent(code: str) -> None:
    assert code not in {f.code for f in lint(make_spec())}


@pytest.mark.parametrize("changes", [dict(space_name=""), dict(network_name=""), dict(space_name="", network_name="")])
def test_name_mismatch_requires_both_names(changes: dict) -> None:
    assert "SPEC-NAME-MISMATCH" not in {f.code for f in lint(make_spec(make_placement(**changes)))}
