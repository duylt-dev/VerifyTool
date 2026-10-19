"""CLI integration with real readers (static-check-spec §2, §8–§9)."""

import shutil
from pathlib import Path

import pytest
from conftest import MINI_APK, UNIT_ID, ad_data, config_data, make_spec_xlsx, write_rc

from apkverify.cli import main


@pytest.mark.parametrize("failed", [False, True])
def test_static_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str], failed: bool) -> None:
    source = tmp_path / "inputs"
    source.mkdir()
    shutil.copyfile(MINI_APK, source / "mini.apk")
    make_spec_xlsx(
        source / "spec.xlsx",
        [
            {
                "Định Dạng": "Native",
                "Config Name": "home_bottom",
                "Ad Space": "home_bottom_native",
                "Network Ad Name": "Am_home_bottom_native",
                "ID": UNIT_ID,
            }
        ],
    )
    write_rc(source / "admob_id.json", ad_data(listAds=[]) if failed else ad_data())
    write_rc(source / "config_show_ads.json", config_data())
    out = tmp_path / "reports"
    assert main(["static", "--input", str(source), "--out", str(out)]) == (1 if failed else 0)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "apkverify 0.1.0: kiểm tra tĩnh\nAPK:  mini.apk" in captured.out
    assert "Spec: spec.xlsx (1 vị trí)" in captured.out
    assert "Remote Config: admob_id.json, config_show_ads.json\n\n" in captured.out
    if failed:
        assert "KẾT LUẬN: KHÔNG ĐẠT: 1 lỗi" in captured.out
        assert "  [RC-SPACE-MISSING]" in captured.out
    else:
        # mini.apk intentionally has an empty config_show_ads fallback asset.
        assert "KẾT LUẬN: ĐẠT: 0 lỗi, 1 cảnh báo, 0 thông tin" in captured.out
    reports = list(out.glob("*.html"))
    assert len(reports) == 1
    assert captured.out.endswith(f"\n\nBáo cáo: {reports[0]}\n")


def test_missing_apk(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["static", "--input", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "Lỗi: Không thấy file .apk" in captured.err
    assert captured.out == ""


def test_no_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage: apkverify" in capsys.readouterr().out


@pytest.mark.real_input
def test_real_input_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["static", "--input", "input", "--out", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "[APK-SPACE-MISSING] Code không gọi Ad Space 'splash_interstitial'" in captured.out
    assert "KẾT LUẬN: KHÔNG ĐẠT: 1 lỗi, 18 cảnh báo, 6 thông tin" in captured.out
    assert captured.err == ""
    reports = list(tmp_path.glob("*.html"))
    assert len(reports) == 1
    assert captured.out.endswith(f"Báo cáo: {reports[0]}\n")
