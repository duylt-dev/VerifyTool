"""Vietnamese terminal output: the only module that prints (LLM.md §2)."""

import os
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path

from apkverify import __version__
from apkverify.errors import VerifyError
from apkverify.model import AdEvent, ApkFacts, DeviceInfo, RuntimeResult, Severity, StaticResult

APK_REMINDER = "Đây là kiểm tra trên source. Trước khi gửi MO vẫn chạy `apkverify static` trên APK release."


def setup() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def device(info: DeviceInfo) -> None:
    print(f"Thiết bị: {info.serial} ({info.model}, Android {info.android})")
    if not info.emulator:
        print("Máy thật: phải đăng ký test device trên AdMob trước khi bấm quảng cáo (rủi ro invalid traffic).")
    print("Đang theo dõi quảng cáo. Bấm qua app; nhấn Enter (hoặc Ctrl+C) để kết thúc.")


def event(item: AdEvent) -> None:
    if item.event != "start load":
        stamp = datetime.fromtimestamp(item.time).strftime("%H:%M:%S")
        error = f"  {item.code} {item.message}" if item.code else ""
        print(f"{stamp}  {item.event:<14} {item.source:<26} {' / '.join(item.names)}{error}", flush=True)


def _build_line(apk: ApkFacts) -> str:
    if apk.project is None:
        return f"APK:  {apk.file_name} ({apk.package} {apk.version_name}, versionCode {apk.version_code})"
    version = f"{apk.package or '?'} {apk.version_name or '?'}, versionCode {apk.version_code or '?'}"
    return f"Project: {apk.project.root} (module {apk.project.app_module}, {version})"


def interactive() -> bool:
    """Questions need a person at a terminal; in CI a missing flag is a usage error instead of a hang."""
    return sys.stdin.isatty()


def project(apk: ApkFacts) -> None:
    """Shown before the questions, so the developer sees which project and module will be checked."""
    print(f"apkverify {__version__}: kiểm tra project")
    print(_build_line(apk))
    print()


def clean_path(text: str, windows: bool = os.name == "nt") -> Path:
    """A path as typed or dropped into a terminal: quotes, PowerShell's "& '…'" and, off Windows, "\\ " escapes."""
    text = text.strip()
    if text.startswith("& "):
        text = text[2:].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1]
    elif not windows and "\\" in text and not Path(text).expanduser().exists():
        text = re.sub(r"\\(.)", r"\1", text)
    return Path(text).expanduser()


def ask_path(number: int, question: str, suffix: str, default: Path | None) -> Path:
    """Ask until the answer is an existing `suffix` file; Enter takes `default`. EOF stops like Ctrl+C."""
    hint = f" [Enter = {default}]" if default else ""
    while True:
        try:
            answer = input(f"{number}/3 {question}{hint}: ")
        except EOFError:
            raise KeyboardInterrupt from None
        if not answer.strip():
            if default:
                return default
            print("   Chưa nhập đường dẫn.")
            continue
        path = clean_path(answer)
        if not path.is_file():
            print(f"   Không thấy file: {path}")
        elif path.suffix.lower() != suffix:
            print(f"   Cần file {suffix}: {path.name}")
        else:
            return path


def summary(result: StaticResult | RuntimeResult, report: Path, sources: str = "") -> None:
    apk, spec = result.apk, result.spec
    runtime = isinstance(result, RuntimeResult)
    if not runtime:
        sources = ", ".join(dict.fromkeys(value.source for value in result.rc_values)) or "(không có)"
    kind = "kiểm tra lúc chạy" if runtime else "kiểm tra tĩnh" if apk.project is None else "kiểm tra project"
    print(f"apkverify {__version__}: {kind}")
    print(_build_line(apk))
    print(f"Spec: {spec.file_name} ({len(spec.placements)} vị trí)")
    if sources:
        print(f"Remote Config: {sources}")
    elif runtime:
        print(f"Thiết bị: {result.device.serial} ({result.device.model}, Android {result.device.android})")
    print()
    verdict = "ĐẠT" if result.passed else "KHÔNG ĐẠT"
    print(
        f"KẾT LUẬN: {verdict}: {result.count(Severity.ERROR)} lỗi, "
        f"{result.count(Severity.WARN)} cảnh báo, {result.count(Severity.INFO)} thông tin"
    )
    for finding in result.findings:
        if finding.severity == Severity.ERROR:
            print(f"  [{finding.code}] {finding.message}")
    print()
    print(f"Báo cáo: {report}")
    if runtime:
        print(f"Log: {report.parent / result.log_file}")
    if apk.project is not None:
        print(APK_REMINDER)


def error(problem: VerifyError, verbose: bool) -> None:
    print(f"Lỗi: {problem}", file=sys.stderr)
    if verbose:
        traceback.print_exc()


def stopped() -> None:
    print("Đã dừng.", file=sys.stderr)
