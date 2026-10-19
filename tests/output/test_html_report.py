"""HTML output contract: static-check-spec §7–§8."""

from datetime import datetime
from pathlib import Path

import pytest
from conftest import make_apk_facts, make_placement, make_project_facts, make_spec

from apkverify.model import Finding, PlacementStatus, RcValue, Severity, StaticResult
from apkverify.output.html_report import PROJECT_NOTICE, report_path, write_static

NOW = datetime(2026, 10, 5, 12, 34, 56)


@pytest.mark.parametrize("failed", [False, True])
def test_static_report(tmp_path: Path, failed: bool) -> None:
    placements = (
        make_placement(
            row=5,
            task="First placement",
            note="<script>alert(1)</script>",
            group_note="Group <note>\nsecond line",
            link="javascript:alert(1)",
        ),
        make_placement(row=8, task="Second placement", group="Splash", link="https://app.clickup.com/t/123"),
    )
    findings = (
        Finding("RC-CONFIG-OFF", Severity.WARN, "Config tắt", (5,)),
        Finding("SPEC-NAME-MISMATCH", Severity.INFO, "Tên khác", (8,)),
    )
    if failed:
        findings = (Finding("APK-SPACE-MISSING", Severity.ERROR, "Thiếu space", (5, 8)),) + findings
    result = StaticResult(
        make_spec(*placements),
        make_apk_facts(),
        (RcValue("admob_id", "{}", "admob_id.json"),),
        findings,
        tuple(PlacementStatus(p, "OK", "TẮT", "THIẾU", "—", "LỖI") for p in placements),
    )
    out = tmp_path / "nested" / "reports"
    path = write_static(result, out, NOW)
    html = path.read_text(encoding="utf-8")
    assert path.name == "com.example.mini_1.0-mini_20261005-123456_static.html"
    assert not list(out.glob("*.tmp"))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>" not in html
    assert '<a href="javascript:' not in html
    assert '<a href="https://app.clickup.com/t/123">' in html
    assert "Group &lt;note&gt;\nsecond line" in html
    assert "KHÔNG ĐẠT: 1 lỗi" in html if failed else "<h1>ĐẠT</h1>" in html
    if not failed:
        assert "Không có." in html
    for placement in placements:
        assert f"<td>{placement.row}</td><td>{placement.task}</td>" in html
    for finding in findings:
        assert finding.code in html
    assert "Dòng 5, 8" in html if failed else "Dòng 5" in html
    assert "admob_id</code> → admob_id.json" in html
    assert "<code>" + result.apk.sha256 + "</code>" in html
    assert '<td class="status good">OK</td>' in html
    assert '<td class="status warn">TẮT</td>' in html
    assert '<td class="status bad">THIẾU</td>' in html
    assert '<td class="status muted">—</td>' in html
    second = write_static(result, out, NOW)
    assert second.name == path.stem + "-2.html"
    assert path.read_text(encoding="utf-8") == html
    assert not list(out.glob("*.tmp"))


def test_report_path_sanitizes_and_preserves_existing_files(tmp_path: Path) -> None:
    first = report_path(tmp_path, "co:app/name", "dev:1/2", NOW, "sta:tic")
    assert first.name == "co_app_name_dev_1_2_20261005-123456_sta_tic.html"
    first.write_text("existing", encoding="utf-8")
    second = report_path(tmp_path, "co:app/name", "dev:1/2", NOW, "sta:tic")
    assert second.name == first.stem + "-2.html"
    second.write_text("second", encoding="utf-8")
    third = report_path(tmp_path, "co:app/name", "dev:1/2", NOW, "sta:tic")
    assert third.name == first.stem + "-3.html"
    assert first.read_text(encoding="utf-8") == "existing"


def test_project_report(tmp_path: Path) -> None:
    placement = make_placement()
    result = StaticResult(
        make_spec(placement),
        make_project_facts(package="", version_name="", project={"ad_library": "com.github.piontech96:Dolphin-Ads:1"}),
        (),
        (),
        (PlacementStatus(placement, "OK", "BẬT", "OK", "OK", "ĐẠT"),),
    )
    path = write_static(result, tmp_path, NOW)
    html = path.read_text(encoding="utf-8")
    assert path.name == "Mini__20261005-123456_project.html"
    assert f'<p class="warn">{PROJECT_NOTICE}</p>' in html
    for label, value in (
        ("Project", "/work/Mini"),
        ("Module ứng dụng", ":app"),
        ("Thư viện quảng cáo", "com.github.piontech96:Dolphin-Ads:1"),
        ("File code đã đọc", "3"),
        ("Package", "—"),
        ("versionName", "—"),
    ):
        assert f"<dt>{label}</dt><dd>{value}</dd>" in html
    assert "SHA-256" not in html and "Kích thước" not in html


def test_apk_report_has_no_project_notice(tmp_path: Path) -> None:
    placement = make_placement()
    result = StaticResult(make_spec(placement), make_apk_facts(), (), (), ())
    assert PROJECT_NOTICE not in write_static(result, tmp_path, NOW).read_text(encoding="utf-8")
