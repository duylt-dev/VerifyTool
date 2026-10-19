"""Explicit and discovered file selection (static-check-spec §2)."""

from pathlib import Path

import pytest

from apkverify.errors import InputError
from apkverify.inputs import InputSet, discover


def test_discovery_sorted_direct_files_and_excel_lock(tmp_path: Path) -> None:
    for name in ("a.apk", "a.xlsx", "~$a.xlsx", "z.json", "a.json"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/other.apk").write_bytes(b"")
    (tmp_path / "directory.apk").mkdir()
    assert discover(tmp_path) == InputSet(
        tmp_path / "a.apk", tmp_path / "a.xlsx", (tmp_path / "a.json", tmp_path / "z.json")
    )


def test_explicit_inputs_replace_discovery(tmp_path: Path) -> None:
    for name in ("a.apk", "b.apk", "a.xlsx", "b.xlsx", "z.json", "a.json"):
        (tmp_path / name).write_bytes(b"")
    explicit = (tmp_path / "z.json", tmp_path / "a.json")
    result = discover(tmp_path / "absent", tmp_path / "b.apk", tmp_path / "b.xlsx", explicit)
    assert result == InputSet(tmp_path / "b.apk", tmp_path / "b.xlsx", explicit)
    assert discover(tmp_path, result.apk, result.spec, []).rc_files == ()


def test_missing_directory(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    with pytest.raises(InputError) as error:
        discover(missing)
    assert str(error.value) == f"Không thấy thư mục input: {missing}."


@pytest.mark.parametrize("kind", ["apk", "spec", "rc"])
def test_missing_explicit_path(tmp_path: Path, kind: str) -> None:
    apk, spec, rc = tmp_path / "a.apk", tmp_path / "a.xlsx", tmp_path / "a.json"
    for path in (apk, spec, rc):
        path.write_bytes(b"")
    missing = tmp_path / "absent"
    with pytest.raises(InputError) as error:
        discover(
            tmp_path,
            missing if kind == "apk" else apk,
            missing if kind == "spec" else spec,
            [missing if kind == "rc" else rc],
        )
    assert str(error.value) == f"Không thấy file: {missing}."


@pytest.mark.parametrize("suffix,flag", [(".apk", "--apk"), (".xlsx", "--spec")])
@pytest.mark.parametrize("count", [0, 2])
def test_zero_or_multiple(tmp_path: Path, suffix: str, flag: str, count: int) -> None:
    (tmp_path / ("valid.xlsx" if suffix == ".apk" else "valid.apk")).write_bytes(b"")
    for name in ("z", "a")[:count]:
        (tmp_path / f"{name}{suffix}").write_bytes(b"")
    with pytest.raises(InputError) as error:
        discover(tmp_path)
    expected = (
        f"Không thấy file {suffix} nào trong {tmp_path}. Chỉ rõ bằng {flag}."
        if count == 0
        else f"Có 2 file {suffix} trong {tmp_path}: a{suffix}, z{suffix}. Chỉ rõ bằng {flag}."
    )
    assert str(error.value) == expected


def test_no_json_is_valid_and_lock_prefix_only_applies_to_excel(tmp_path: Path) -> None:
    (tmp_path / "~$a.apk").write_bytes(b"")
    (tmp_path / "a.xlsx").write_bytes(b"")
    result = discover(tmp_path)
    assert result.apk.name == "~$a.apk" and result.rc_files == ()
