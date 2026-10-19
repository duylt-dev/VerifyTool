"""Vietnamese terminal output: the only module that prints (LLM.md §2)."""

import sys
import traceback
from datetime import datetime
from pathlib import Path

from apkverify import __version__
from apkverify.errors import VerifyError
from apkverify.model import AdEvent, DeviceInfo, RuntimeResult, Severity, StaticResult


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


def summary(result: StaticResult | RuntimeResult, report: Path, sources: str = "") -> None:
    apk, spec = result.apk, result.spec
    runtime = isinstance(result, RuntimeResult)
    if not runtime:
        sources = ", ".join(dict.fromkeys(value.source for value in result.rc_values)) or "(không có)"
    print(f"apkverify {__version__}: {'kiểm tra lúc chạy' if runtime else 'kiểm tra tĩnh'}")
    print(f"APK:  {apk.file_name} ({apk.package} {apk.version_name}, versionCode {apk.version_code})")
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


def error(problem: VerifyError, verbose: bool) -> None:
    print(f"Lỗi: {problem}", file=sys.stderr)
    if verbose:
        traceback.print_exc()


def stopped() -> None:
    print("Đã dừng.", file=sys.stderr)
