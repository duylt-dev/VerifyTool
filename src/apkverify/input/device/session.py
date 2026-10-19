"""Stream a session to disk and stop logcat on Enter, Ctrl+C or a timer (LLM.md §7)."""

import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from apkverify.input.device.adb import Adb
from apkverify.input.device.log_parser import parse_line
from apkverify.model import AdEvent


def run_session(
    adb: Adb,
    apk_path: Path,
    package: str,
    *,
    install: bool,
    fresh: bool,
    duration: float | None,
    log_path: Path,
    on_event: Callable[[AdEvent], None],
    stop_on_enter: bool = True,
) -> tuple[list[AdEvent], float, float]:
    if install:
        adb.install(apk_path)
    if fresh:
        adb.clear_data(package)
    adb.force_stop(package)
    adb.clear_log()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    events: list[AdEvent] = []
    timer = None
    stopped = threading.Event()
    proc = adb.start_logcat()

    def stop() -> None:
        stopped.set()
        adb.stop(proc)

    def wait_enter() -> None:
        if sys.stdin.readline():
            stop()

    try:
        adb.launch(package)
        started = time.time()
        if stop_on_enter:
            threading.Thread(target=wait_enter, daemon=True).start()
        if duration is not None:
            timer = threading.Timer(duration, stop)
            timer.daemon = True
            timer.start()
        with log_path.open("a", encoding="utf-8") as stream:
            try:
                assert proc.stdout is not None
                for line in proc.stdout:
                    stream.write(line)
                    stream.flush()
                    if event := parse_line(line):
                        events.append(event)
                        on_event(event)
            except KeyboardInterrupt:
                stop()
            ended = time.time()
        if not stopped.is_set():
            adb.check_logcat(proc, log_path)
        return events, started, ended
    finally:
        adb.stop(proc)
        if timer is not None:
            timer.cancel()
        if proc.stdout is not None:
            proc.stdout.close()
