"""Command-line entry point and Vietnamese terminal output."""

import argparse
import logging
import math
import sys
import traceback
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from apkverify import __version__
from apkverify.apk_reader import read_apk
from apkverify.checks.static_result import build
from apkverify.errors import VerifyError
from apkverify.inputs import discover
from apkverify.model import AdEvent, RuntimeResult, Severity, StaticResult
from apkverify.rc_reader import read_rc_files
from apkverify.report.html_report import report_path, write_runtime, write_static
from apkverify.runtime.adb import find_adb, pick_device
from apkverify.runtime.runtime_checks import build_runtime
from apkverify.runtime.session import run_session
from apkverify.spec_reader import read_spec


def _summary(result: StaticResult | RuntimeResult, report: Path, sources: str = "") -> None:
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


def _on_event(event: AdEvent) -> None:
    if event.event != "start load":
        stamp = datetime.fromtimestamp(event.time).strftime("%H:%M:%S")
        error = f"  {event.code} {event.message}" if event.code else ""
        print(f"{stamp}  {event.event:<14} {event.source:<26} {' / '.join(event.names)}{error}", flush=True)


def _duration(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("--duration phải là số giây hữu hạn lớn hơn 0.")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="apkverify")
    commands = parser.add_subparsers(dest="command")
    static = commands.add_parser("static", help="Kiểm tra tĩnh APK theo spec và Remote Config")
    runtime = commands.add_parser("runtime", help="Kiểm tra quảng cáo lúc chạy trên thiết bị")
    for command in (static, runtime):
        command.add_argument("--input", type=Path, default=Path("input"), metavar="DIR")
        command.add_argument("--apk", type=Path)
        command.add_argument("--spec", type=Path)
        command.add_argument("--rc", type=Path, nargs="+", metavar="FILE")
        command.add_argument("--out", type=Path, default=Path("output"), metavar="DIR")
        command.add_argument("-v", "--verbose", action="store_true")
    runtime.add_argument("--serial")
    runtime.add_argument("--no-install", action="store_true")
    runtime.add_argument("--fresh", action="store_true")
    runtime.add_argument("--duration", type=_duration, metavar="SECONDS")
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)
    try:
        inputs = discover(args.input, args.apk, args.spec, args.rc)
        spec = read_spec(inputs.spec)
        remote = read_rc_files(inputs.rc_files)
        apk = read_apk(inputs.apk)
        sources = ""
        if args.command == "runtime":
            adb = pick_device(find_adb(), args.serial)
            device = adb.device_info()
            print(f"Thiết bị: {device.serial} ({device.model}, Android {device.android})")
            if not device.emulator:
                print("Máy thật: phải đăng ký test device trên AdMob trước khi bấm quảng cáo (rủi ro invalid traffic).")
            now = datetime.now()
            log_path = report_path(args.out, apk.package, apk.version_name, now, "runtime").with_suffix(".log")
            print("Đang theo dõi quảng cáo. Bấm qua app; nhấn Enter (hoặc Ctrl+C) để kết thúc.")
            events, started, ended = run_session(
                adb,
                inputs.apk,
                apk.package,
                install=not args.no_install,
                fresh=args.fresh,
                duration=args.duration,
                log_path=log_path,
                on_event=_on_event,
            )
            result = build_runtime(spec, remote, apk, device, events, started, ended, log_path.name)
            report = write_runtime(result, args.out, now)
            sources = ", ".join(dict.fromkeys(value.source for value in remote))
        else:
            result = build(spec, remote, apk)
            report = write_static(result, args.out, datetime.now())
        _summary(result, report, sources)
        return 0 if result.passed else 1
    except VerifyError as error:
        print(f"Lỗi: {error}", file=sys.stderr)
        if args.verbose:
            traceback.print_exc()
        return 2
    except KeyboardInterrupt:
        print("Đã dừng.", file=sys.stderr)
        return 130


def run() -> None:
    sys.exit(main())
