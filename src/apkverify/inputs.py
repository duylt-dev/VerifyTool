"""Discover input files without choosing between ambiguous builds (§2)."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from apkverify.errors import InputError


@dataclass(frozen=True, slots=True)
class InputSet:
    apk: Path
    spec: Path
    rc_files: tuple[Path, ...]


def _explicit(path: Path) -> Path:
    if not path.is_file():
        raise InputError(f"Không thấy file: {path}.")
    return path


def _single(directory: Path, suffix: str, flag: str) -> Path:
    paths = sorted(
        p for p in directory.glob(f"*{suffix}") if p.is_file() and not (suffix == ".xlsx" and p.name.startswith("~$"))
    )
    if not paths:
        raise InputError(f"Không thấy file {suffix} nào trong {directory}. Chỉ rõ bằng {flag}.")
    if len(paths) > 1:
        names = ", ".join(p.name for p in paths)
        raise InputError(f"Có {len(paths)} file {suffix} trong {directory}: {names}. Chỉ rõ bằng {flag}.")
    return paths[0]


def discover(
    input_dir: Path, apk: Path | None = None, spec: Path | None = None, rc: Sequence[Path] | None = None
) -> InputSet:
    if (apk is None or spec is None or rc is None) and not input_dir.is_dir():
        raise InputError(f"Không thấy thư mục input: {input_dir}.")
    apk_path = _explicit(apk) if apk is not None else _single(input_dir, ".apk", "--apk")
    spec_path = _explicit(spec) if spec is not None else _single(input_dir, ".xlsx", "--spec")
    rc_paths = (
        tuple(_explicit(p) for p in rc)
        if rc is not None
        else tuple(sorted(p for p in input_dir.glob("*.json") if p.is_file()))
    )
    return InputSet(apk_path, spec_path, rc_paths)
