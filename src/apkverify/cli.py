"""Command-line entry point: parse arguments, then run input → process → output."""

import argparse
import logging
import math
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from apkverify.errors import VerifyError
from apkverify.input.apk_reader import read_apk
from apkverify.input.device.adb import find_adb, pick_device
from apkverify.input.device.session import run_session
from apkverify.input.discover import discover
from apkverify.input.rc_reader import read_rc_files
from apkverify.input.spec_reader import read_spec
from apkverify.output import console
from apkverify.output.html_report import report_path, write_runtime, write_static
from apkverify.process.runtime.runtime_checks import build_runtime
from apkverify.process.static.static_result import build


def _duration(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("--duration phải là số giây hữu hạn lớn hơn 0.")
    return number


def main(argv: Sequence[str] | None = None) -> int:
    console.setup()
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
            console.device(device)
            now = datetime.now()
            log_path = report_path(args.out, apk.package, apk.version_name, now, "runtime").with_suffix(".log")
            events, started, ended = run_session(
                adb,
                inputs.apk,
                apk.package,
                install=not args.no_install,
                fresh=args.fresh,
                duration=args.duration,
                log_path=log_path,
                on_event=console.event,
            )
            result = build_runtime(spec, remote, apk, device, events, started, ended, log_path.name)
            report = write_runtime(result, args.out, now)
            sources = ", ".join(dict.fromkeys(value.source for value in remote))
        else:
            result = build(spec, remote, apk)
            report = write_static(result, args.out, datetime.now())
        console.summary(result, report, sources)
        return 0 if result.passed else 1
    except VerifyError as error:
        console.error(error, args.verbose)
        return 2
    except KeyboardInterrupt:
        console.stopped()
        return 130


def run() -> None:
    sys.exit(main())
