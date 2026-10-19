"""Pure placement matching and status rows (runtime-check-spec §5)."""

from collections.abc import Sequence

from apkverify.model import AdEvent, Finding, Placement, RuntimeStatus, Severity


def placement_name(placement: Placement) -> str:
    return placement.space_name if placement.has_id else placement.config_name


def placement_events(placement: Placement, events: Sequence[AdEvent]) -> list[AdEvent]:
    name = placement_name(placement)
    return [event for event in events if name and name in event.names]


def build_status(placement: Placement, events: Sequence[AdEvent], findings: Sequence[Finding]) -> RuntimeStatus:
    matched = placement_events(placement, events)
    kinds = {event.event for event in matched}
    if "show success" in kinds:
        status = "ĐÃ SHOW"
    elif "load success" in kinds:
        status = "ĐÃ LOAD"
    elif kinds & {"load failed", "show failed"}:
        status = "LỖI"
    elif matched:
        status = "ĐÃ REQUEST"
    else:
        status = "CHƯA THẤY"
    severity = max((f.severity for f in findings if placement.row in f.rows), default=Severity.INFO)
    verdict = "LỖI" if severity == Severity.ERROR else "CẢNH BÁO" if severity == Severity.WARN else "ĐẠT"
    errors = tuple(dict.fromkeys(f"{e.code} {e.message}".strip() for e in matched if "failed" in e.event))
    return RuntimeStatus(
        placement,
        status,
        sum(e.event == "show success" for e in matched),
        min((e.time for e in matched), default=None),
        max((e.time for e in matched), default=None),
        errors,
        verdict,
    )
