"""`apkverify project` end to end on a real mini project (static-check-spec §5.1, §8)."""

import json
from pathlib import Path

import pytest
from conftest import UNIT_ID, ad_data, config_data, make_project, make_spec_xlsx, write_rc

from apkverify.cli import main
from apkverify.output import console

SPEC_ROW = {
    "Định Dạng": "Native",
    "Config Name": "home_bottom",
    "Ad Space": "home_bottom_native",
    "Network Ad Name": "Am_home_bottom_native",
    "ID": UNIT_ID,
}


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    return {
        "project": make_project(tmp_path / "Mini"),
        "admob_id": write_rc(downloads / "admob_id (1).json", ad_data()),
        "config_show_ads": write_rc(downloads / "config_show_ads.json", config_data()),
        "spec": make_spec_xlsx(downloads / "spec.xlsx", [SPEC_ROW]),
    }


def _flags(files: dict[str, Path]) -> list[str]:
    return [
        "--admob-id",
        str(files["admob_id"]),
        "--config-show-ads",
        str(files["config_show_ads"]),
        "--spec",
        str(files["spec"]),
    ]


@pytest.mark.parametrize("failed", [False, True])
def test_project_with_flags(files: dict[str, Path], capsys: pytest.CaptureFixture[str], failed: bool) -> None:
    if failed:
        write_rc(files["admob_id"], ad_data(listAds=[]))
    root = files["project"]
    assert main(["project", "--project", str(root / "app"), *_flags(files)]) == (1 if failed else 0)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out.startswith(
        "apkverify 0.2.0: kiểm tra project\n"
        f"Project: {root} (module :app, com.example.mini 1.0-mini, versionCode 7)\n"
        "Spec: spec.xlsx (1 vị trí)\n"
        "Remote Config: admob_id (1).json, config_show_ads.json\n\n"
    )
    out = root / "build" / "apkverify"
    reports = list(out.glob("*_project.html"))
    assert len(reports) == 1
    if failed:
        assert "KẾT LUẬN: KHÔNG ĐẠT: 1 lỗi" in captured.out and "  [RC-SPACE-MISSING]" in captured.out
    else:
        # Fallbacks are found in two modules: admob_id.txt in app, config_show_ads.txt in LibAds.
        assert "KẾT LUẬN: ĐẠT: 0 lỗi, 0 cảnh báo, 0 thông tin" in captured.out
    assert captured.out.endswith(f"Báo cáo: {reports[0]}\n{console.APK_REMINDER}\n")
    remembered = json.loads((out / "last-inputs.json").read_text(encoding="utf-8"))
    assert remembered == {key: str(files[key].resolve()) for key in ("admob_id", "config_show_ads", "spec")}


def test_missing_flag_without_a_terminal(files: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    args = ["project", "--project", str(files["project"]), "--admob-id", str(files["admob_id"])]
    assert main(args) == 2
    assert capsys.readouterr().err == (
        "Lỗi: Thiếu --config-show-ads FILE: chạy lệnh trong terminal để được hỏi, hoặc truyền đường dẫn.\n"
    )
    assert not (files["project"] / "build").exists()


def test_not_a_project(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["project", "--project", str(tmp_path)]) == 2
    assert "Lỗi: Không thấy project Android" in capsys.readouterr().err


def test_flag_file_missing(files: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    files["spec"].unlink()
    assert main(["project", "--project", str(files["project"]), *_flags(files)]) == 2
    assert f"Lỗi: Không thấy file: {files['spec']}." in capsys.readouterr().err


def test_questions_then_remembered_answers(
    files: dict[str, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "interactive", lambda: True)
    replies = iter([f'"{files["admob_id"]}"', str(files["config_show_ads"]), str(files["spec"]), "", "", ""])
    prompts: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or next(replies))
    out = tmp_path / "reports"
    args = ["project", "--project", str(files["project"]), "--out", str(out)]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert first.startswith(f"apkverify 0.2.0: kiểm tra project\nProject: {files['project']} (module :app")
    assert prompts == [
        "1/3 Đường dẫn file admob_id.json (giá trị Remote Config key admob_id): ",
        "2/3 Đường dẫn file config_show_ads.json (giá trị Remote Config key config_show_ads): ",
        "3/3 Đường dẫn file spec quảng cáo của MO (.xlsx): ",
    ]
    assert main(args) == 0
    assert [prompt.split(" [Enter = ")[1] for prompt in prompts[3:]] == [
        f"{files[key].resolve()}]: " for key in ("admob_id", "config_show_ads", "spec")
    ]
    assert len(list(out.glob("*_project*.html"))) == 2  # same second: "…_project-2.html"


def test_flags_given_skip_their_questions(
    files: dict[str, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(console, "interactive", lambda: True)
    prompts: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or str(files["spec"]))
    args = ["project", "--project", str(files["project"]), *_flags(files)[:4]]
    assert main(args) == 0
    assert prompts == ["3/3 Đường dẫn file spec quảng cáo của MO (.xlsx): "]


def test_flag_with_the_wrong_file_type(files: dict[str, Path], capsys: pytest.CaptureFixture[str]) -> None:
    args = ["project", "--project", str(files["project"]), *_flags(files)]
    args[args.index("--spec") + 1] = str(files["admob_id"])
    assert main(args) == 2
    assert f"Lỗi: --spec cần file .xlsx: {files['admob_id']}." in capsys.readouterr().err
