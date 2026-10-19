"""Terminal questions of `apkverify project` (LLM.md §6)."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from apkverify.output.console import ask_path, clean_path


@pytest.mark.parametrize(
    "text,windows,expected",
    [
        ("  /a/b.json  ", False, "/a/b.json"),
        ("'/a/with space.json'", False, "/a/with space.json"),
        ('"C:\\Users\\dev\\b.json"', True, "C:\\Users\\dev\\b.json"),
        ("& 'C:\\Users\\dev\\b.json'", True, "C:\\Users\\dev\\b.json"),
        ("/a/with\\ space\\ \\(1\\).json", False, "/a/with space (1).json"),
        ("C:\\Users\\dev\\b.json", True, "C:\\Users\\dev\\b.json"),
    ],
)
def test_clean_path(text: str, windows: bool, expected: str) -> None:
    assert str(clean_path(text, windows)) == expected


def test_escaped_text_that_exists_is_kept(tmp_path: Path) -> None:
    literal = tmp_path / "back\\slash.json"
    literal.write_text("{}", encoding="utf-8")
    assert clean_path(str(literal), windows=False) == literal


def _answers(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    prompts: list[str] = []
    replies: Iterator[str] = iter(answers)

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        try:
            return next(replies)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def test_ask_path_retries_until_a_file_of_the_right_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    wanted = tmp_path / "admob_id (1).json"
    wanted.write_text("{}", encoding="utf-8")
    spec = tmp_path / "spec.xlsx"
    spec.write_text("", encoding="utf-8")
    prompts = _answers(monkeypatch, "", str(tmp_path / "missing.json"), str(spec), f"'{wanted}'")
    assert ask_path(1, "Đường dẫn file admob_id.json", ".json", None) == wanted
    assert prompts == ["1/3 Đường dẫn file admob_id.json: "] * 4
    assert capsys.readouterr().out.splitlines() == [
        "   Chưa nhập đường dẫn.",
        f"   Không thấy file: {tmp_path / 'missing.json'}",
        "   Cần file .json: spec.xlsx",
    ]


def test_ask_path_enter_takes_the_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "spec.xlsx"
    prompts = _answers(monkeypatch, "  ")
    assert ask_path(3, "Spec", ".xlsx", default) == default
    assert prompts == [f"3/3 Spec [Enter = {default}]: "]


def test_ask_path_eof_stops_like_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    _answers(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        ask_path(2, "Config", ".json", None)
