"""Command-line entry point: parse arguments, then run input → process → output."""

import argparse
import logging
import math
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from apkverify.errors import InputError, VerifyError
from apkverify.input.apk_reader import read_apk
from apkverify.input.device.adb import find_adb, pick_device
from apkverify.input.device.session import run_session
from apkverify.input.discover import discover
from apkverify.input.project_reader import find_project, read_last_inputs, read_project
from apkverify.input.rc_reader import read_rc_answers, read_rc_files
from apkverify.input.spec_reader import read_spec
from apkverify.model import StaticResult
from apkverify.output import console
from apkverify.output.html_report import report_path, write_runtime, write_static
from apkverify.output.last_inputs import write_last_inputs
from apkverify.process.runtime.runtime_checks import build_runtime
from apkverify.process.static.static_result import build

# `apkverify project`: (answer key = argparse dest, question, required suffix). The two Remote Config keys first.
QUESTIONS = (
    ("admob_id", "Đường dẫn file admob_id.json (giá trị Remote Config key admob_id)", ".json"),
    ("config_show_ads", "Đường dẫn file config_show_ads.json (giá trị Remote Config key config_show_ads)", ".json"),
    ("spec", "Đường dẫn file spec quảng cáo của MO (.xlsx)", ".xlsx"),
)


def _duration(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("--duration phải là số giây hữu hạn lớn hơn 0.")
    return number


def _project(args: argparse.Namespace) -> tuple[StaticResult, Path]:
    """Read the project first, so a wrong directory fails before any question; then ask what no flag gave."""
    apk = read_project(find_project(args.project))
    out = args.out or Path(apk.project.root) / "build" / "apkverify"
    remembered = read_last_inputs(out)
    answers: dict[str, Path] = {}
    asked = False
    for number, (key, question, suffix) in enumerate(QUESTIONS, 1):
        given = getattr(args, key)
        flag = "--" + key.replace("_", "-")
        if given is not None:
            if not given.is_file():
                raise InputError(f"Không thấy file: {given}.")
            if given.suffix.lower() != suffix:
                raise InputError(f"{flag} cần file {suffix}: {given}.")
            answers[key] = given
            continue
        if not console.interactive():
            raise InputError(f"Thiếu {flag} FILE: chạy lệnh trong terminal để được hỏi, hoặc truyền đường dẫn.")
        if not asked:
            console.project(apk)
            asked = True
        answers[key] = console.ask_path(number, question, suffix, remembered.get(key))
    spec = read_spec(answers["spec"])
    remote = read_rc_answers([(key, answers[key]) for key, _, suffix in QUESTIONS if suffix == ".json"])
    result = build(spec, remote, apk)
    report = write_static(result, out, datetime.now())
    write_last_inputs(out, answers)
    return result, report


def main(argv: Sequence[str] | None = None) -> int:
    console.setup()
    parser = argparse.ArgumentParser(prog="apkverify")
    commands = parser.add_subparsers(dest="command")
    static = commands.add_parser("static", help="Kiểm tra tĩnh APK theo spec và Remote Config")
    runtime = commands.add_parser("runtime", help="Kiểm tra quảng cáo lúc chạy trên thiết bị")
    project = commands.add_parser(
        "project", help="Kiểm tra tĩnh project Android Studio (source) theo spec và Remote Config, không cần APK"
    )
    project.add_argument(
        "--project", type=Path, default=Path("."), metavar="DIR", help="project Android (mặc định: thư mục hiện tại)"
    )
    project.add_argument("--admob-id", type=Path, metavar="FILE", help="file admob_id.json; thiếu thì tool hỏi")
    project.add_argument(
        "--config-show-ads", type=Path, metavar="FILE", help="file config_show_ads.json; thiếu thì tool hỏi"
    )
    project.add_argument("--spec", type=Path, metavar="FILE", help="file spec .xlsx của MO; thiếu thì tool hỏi")
    project.add_argument(
        "--out", type=Path, metavar="DIR", help="thư mục báo cáo (mặc định: <project>/build/apkverify)"
    )
    project.add_argument("-v", "--verbose", action="store_true")
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
        if args.command == "project":
            result, report = _project(args)
            console.summary(result, report)
            return 0 if result.passed else 1
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
