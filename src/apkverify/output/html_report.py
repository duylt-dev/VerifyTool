"""Self-contained HTML reports and atomic output (static-check-spec §8)."""

import os
import re
from datetime import datetime
from itertools import groupby
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from apkverify import __version__
from apkverify.model import RuntimeResult, Severity, StaticResult


def report_path(out_dir: Path, package: str, version_name: str, now: datetime, kind: str) -> Path:
    parts = (package, version_name, now.strftime("%Y%m%d-%H%M%S"), kind)
    stem = "_".join(re.sub(r"[^A-Za-z0-9._-]", "_", part) for part in parts)
    path = out_dir / f"{stem}.html"
    suffix = 2
    while path.exists():
        path = out_dir / f"{stem}-{suffix}.html"
        suffix += 1
    return path


def _status_class(value: str) -> str:
    if value in ("OK", "BẬT", "ĐẠT", "ĐÃ SHOW"):
        return "good"
    if value in ("THIẾU", "SAI", "RỖNG", "TEST", "LỖI"):
        return "bad"
    if value in ("TẮT", "CẢNH BÁO", "ĐÃ LOAD", "ĐÃ REQUEST", "CHƯA THẤY"):
        return "warn"
    return "muted"


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def write_static(result: StaticResult, out_dir: Path, now: datetime) -> Path:
    environment = _environment()
    groups = []
    for title, statuses in groupby(result.statuses, key=lambda status: status.placement.group):
        rows = []
        notes = []
        for status in statuses:
            placement = status.placement
            if placement.group_note and placement.group_note not in notes:
                notes.append(placement.group_note)
            cells = (status.rc_id, status.rc_config, status.code_space, status.code_config, status.verdict)
            rows.append(
                dict(
                    placement=placement,
                    cells=[(value, _status_class(value)) for value in cells],
                    href=placement.link if placement.link.startswith("https://") else "",
                )
            )
        groups.append(dict(title=title, note="\n\n".join(notes), rows=rows))
    severities = []
    for severity, style in ((Severity.ERROR, "bad"), (Severity.WARN, "warn"), (Severity.INFO, "muted")):
        findings = [
            dict(code=f.code, message=f.message, rows=", ".join(map(str, f.rows)))
            for f in result.findings
            if f.severity == severity
        ]
        severities.append(dict(name=severity.name, style=style, count=result.count(severity), findings=findings))
    apk, spec = result.apk, result.spec
    inputs = (
        ("APK", apk.file_name),
        ("SHA-256", apk.sha256),
        ("Kích thước", f"{apk.size / 1_000_000:.2f} MB"),
        ("Package", apk.package),
        ("versionName", apk.version_name),
        ("versionCode", apk.version_code),
        ("AdMob App ID", apk.admob_app_id or "—"),
        ("Firebase project", apk.firebase_project_id or "—"),
        ("Firebase app ID", apk.firebase_app_id or "—"),
        ("Spec", spec.file_name),
        ("Sheet", spec.sheet),
        ("Tiêu đề", spec.title),
        ("Số vị trí", len(spec.placements)),
    )
    html = environment.get_template("static.html.j2").render(
        version=__version__,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        verdict="ĐẠT" if result.passed else f"KHÔNG ĐẠT: {result.count(Severity.ERROR)} lỗi",
        verdict_class="good" if result.passed else "bad",
        inputs=inputs,
        sources=[(value.key, value.source) for value in result.rc_values],
        severities=severities,
        groups=groups,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = report_path(out_dir, apk.package, apk.version_name, now, "static")
    return _write(html, path)


def _write(html: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(html)
        stream.flush()
    os.replace(temporary, path)
    return path


def _event_time(timestamp: float | None) -> str:
    return "—" if timestamp is None else datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]


def write_runtime(result: RuntimeResult, out_dir: Path, now: datetime) -> Path:
    environment = _environment()
    environment.filters["event_time"] = _event_time
    environment.filters["status_class"] = _status_class
    device, apk, spec = result.device, result.apk, result.spec
    inputs = (
        ("Thiết bị", device.serial),
        ("Model", device.model),
        ("Android", device.android),
        ("Loại thiết bị", "Emulator" if device.emulator else "Máy thật"),
        ("APK", apk.file_name),
        ("SHA-256", apk.sha256),
        ("Package", apk.package),
        ("versionName", apk.version_name),
        ("versionCode", apk.version_code),
        ("Spec", spec.file_name),
        ("Sheet", spec.sheet),
        ("Tiêu đề", spec.title),
        ("Bắt đầu", datetime.fromtimestamp(result.started).strftime("%Y-%m-%d %H:%M:%S")),
        ("Kết thúc", datetime.fromtimestamp(result.ended).strftime("%Y-%m-%d %H:%M:%S")),
        ("Thời lượng", f"{result.ended - result.started:.2f} giây"),
        ("Số vị trí", len(result.statuses)),
        ("Số sự kiện", len(result.events)),
        ("Log", result.log_file),
    )
    severities = [
        dict(name=s.name, style=style, count=result.count(s), findings=[f for f in result.findings if f.severity == s])
        for s, style in ((Severity.ERROR, "bad"), (Severity.WARN, "warn"), (Severity.INFO, "muted"))
    ]
    html = environment.get_template("runtime.html.j2").render(
        version=__version__,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        verdict="ĐẠT" if result.passed else f"KHÔNG ĐẠT: {result.count(Severity.ERROR)} lỗi",
        verdict_class="good" if result.passed else "bad",
        inputs=inputs,
        severities=severities,
        statuses=result.statuses,
        events=result.events[:2000],
        remaining=max(0, len(result.events) - 2000),
        log_file=result.log_file,
    )
    path = report_path(out_dir, apk.package, apk.version_name, now, "runtime")
    return _write(html, path)
