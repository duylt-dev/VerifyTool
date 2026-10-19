"""Pure runtime findings and result assembly (runtime-check-spec §5)."""

from collections.abc import Sequence

from apkverify.errors import RcFormatError
from apkverify.formats import AD_UNIT_LIST_KEYS, ADS_CONFIG_KEY, allowed_ads_types, log_source_ads_type
from apkverify.model import AdEvent, ApkFacts, DeviceInfo, Finding, RcValue, RuntimeResult, Severity, Spec
from apkverify.rc_reader import parse_ad_unit_list, parse_ads_config
from apkverify.runtime.runtime_status import build_status, placement_events, placement_name

_NON_AD_EVENTS = frozenset({"screen", "fetch-ok", "fetch-failed"})


def _known_names(spec: Spec, rc_values: Sequence[RcValue]) -> tuple[set[str], set[str], set[str]]:
    spaces = {p.space_name for p in spec.placements if p.space_name}
    configs = {p.config_name for p in spec.placements if p.config_name}
    off = set()
    for value in rc_values:
        try:
            if value.key in AD_UNIT_LIST_KEYS:
                spaces.update(u.space_name for u in parse_ad_unit_list(value.key, value.value).units)
            elif value.key == ADS_CONFIG_KEY:
                entries = parse_ads_config(value.value).configs
                configs.update(c.config_name for c in entries)
                off.update(c.config_name for c in entries if not c.is_on)
        except RcFormatError:
            # Invalid optional RC contributes no names; static checks diagnose its JSON.
            continue
    return spaces, configs, off


def _placement_findings(spec: Spec, events: Sequence[AdEvent], spaces: set[str], off: set[str]) -> list[Finding]:
    findings = []
    for p in spec.placements:
        matched = placement_events(p, events)
        name = placement_name(p)
        if any(e.event == "show success" for e in matched):
            continue
        if not matched:
            suffix = " — đang TẮT trên Remote Config" if p.config_name in off else ""
            findings.append(
                Finding(
                    "RT-NOT-SEEN",
                    Severity.WARN,
                    f"Chưa thấy '{name}' (dòng {p.row}){suffix}: chưa đi tới màn này, hoặc vị trí không được gọi.",
                    (p.row,),
                )
            )
        if any(e.event == "load success" for e in matched):
            findings.append(
                Finding("RT-LOADED-NOT-SHOWN", Severity.WARN, f"'{name}' đã load nhưng chưa show.", (p.row,))
            )
        if not (p.has_id and p.has_config):
            continue
        own_spaces = {other.space_name for other in spec.placements if other.config_name == p.config_name}
        for event in events:
            if (
                event.event != "show success"
                or p.config_name not in event.names
                or log_source_ads_type(event.source) not in (allowed_ads_types(p.format) or ())
            ):
                continue
            for actual in event.names:
                if actual in spaces and actual not in own_spaces:
                    findings.append(
                        Finding(
                            "RT-WRONG-SPACE",
                            Severity.ERROR,
                            f"'{p.config_name}' (dòng {p.row}) show bằng Ad Space '{actual}' thay vì "
                            f"'{p.space_name}': ID {p.ad_id} không được dùng.",
                            (p.row,),
                        )
                    )
    return findings


def _event_findings(
    spec: Spec,
    events: Sequence[AdEvent],
    spaces: set[str],
    configs: set[str],
) -> list[Finding]:
    findings = []
    shown = {name for event in events if event.event == "show success" for name in event.names}
    for event in events:
        if event.event == "fetch-failed":
            findings.append(
                Finding(
                    "RT-RC-FETCH-FAILED",
                    Severity.ERROR,
                    "Fetch Remote Config lỗi: thư viện không đọc danh sách ID nên không quảng cáo nào có ID.",
                )
            )
        if event.structured:
            findings.extend(
                Finding("RT-EXTRA", Severity.WARN, f"Thừa lúc chạy: '{name}' có trong log nhưng không có trong spec.")
                for name in event.names
                if name not in spaces | configs
            )
        if event.event not in ("show failed", "load failed"):
            continue
        targets = [name for name in event.names if name in spaces]
        targets.extend(
            p.config_name
            for p in spec.placements
            if not p.has_id and p.config_name in event.names and p.config_name not in targets
        )
        if not targets:
            targets = list(event.names[-1:])
        config = next((name for name in event.names if name in configs), "")
        for name in targets:
            rows = tuple(p.row for p in spec.placements if placement_name(p) == name)
            if event.event == "show failed" and event.code == "101" and event.message == "ad unit not found":
                config = config or next((p.config_name for p in spec.placements if p.space_name == name), "")
                findings.append(
                    Finding(
                        "RT-UNIT-NOT-FOUND",
                        Severity.ERROR,
                        f"Thiếu ID lúc chạy: '{name}' (config '{config}') không có trong danh sách ad unit.",
                        rows,
                    )
                )
            elif name not in shown:
                action = "show" if event.event == "show failed" else "load"
                findings.append(
                    Finding(
                        f"RT-{action.upper()}-FAILED",
                        Severity.ERROR if action == "show" else Severity.WARN,
                        f"'{name}' {action} lỗi: {event.code} {event.message.rstrip('.')}.",
                        rows,
                    )
                )
    return findings


def _refresh_findings(spec: Spec, events: Sequence[AdEvent], spaces: set[str]) -> list[Finding]:
    findings = []
    for space in sorted(spaces):
        times = sorted(e.time for e in events if e.event == "show success" and space in e.names)
        if len(times) < 5:
            continue
        left = largest = 0
        for right, timestamp in enumerate(times):
            while timestamp - times[left] > 30:
                left += 1
            largest = max(largest, right - left + 1)
        if largest >= 5:
            gap = min(b - a for a, b in zip(times, times[1:], strict=False))
            findings.append(
                Finding(
                    "RT-FAST-REFRESH",
                    Severity.WARN,
                    f"'{space}' show {largest} lần trong 30 giây (khoảng cách ngắn nhất {gap:.2f}s): "
                    "kiểm tra logic reload; AdMob khuyến nghị không refresh nhanh hơn 30 giây.",
                    tuple(p.row for p in spec.placements if p.space_name == space),
                )
            )
    return findings


def build_runtime(
    spec: Spec,
    rc_values: Sequence[RcValue],
    apk: ApkFacts,
    device: DeviceInfo,
    events: Sequence[AdEvent],
    started: float,
    ended: float,
    log_file: str,
) -> RuntimeResult:
    spaces, configs, off = _known_names(spec, rc_values)
    findings = _placement_findings(spec, events, spaces, off)
    findings.extend(_event_findings(spec, events, spaces, configs))
    findings.extend(_refresh_findings(spec, events, spaces))
    if not any(e.event not in _NON_AD_EVENTS for e in events):
        findings.append(
            Finding(
                "RT-NO-EVENTS",
                Severity.ERROR,
                "Không thấy sự kiện quảng cáo nào trong phiên: app không chạy tới quảng cáo, hoặc bản build không "
                "ghi log TESTERADSEVENT. Phiên này không đủ để kết luận.",
            )
        )
    findings = sorted(set(findings), key=lambda f: (-f.severity, f.code, f.rows[0] if f.rows else 0, f.message))
    statuses = tuple(build_status(p, events, findings) for p in spec.placements)
    return RuntimeResult(spec, apk, device, started, ended, tuple(events), tuple(findings), statuses, log_file)
