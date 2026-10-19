"""MO spec findings (static-check-spec §6.1)."""

from collections import defaultdict

from apkverify import formats
from apkverify.model import Finding, Severity, Spec


def lint(spec: Spec) -> list[Finding]:
    findings = []
    ids: dict[str, list[int]] = defaultdict(list)
    spaces: dict[str, list[int]] = defaultdict(list)
    publishers = set()
    for p in spec.placements:

        def warn(code: str, message: str, row: int = p.row) -> None:
            findings.append(Finding(code, Severity.WARN, message, (row,)))

        if not p.has_config and not p.has_id:
            warn("SPEC-NO-KEY", f"Dòng {p.row}: có Định Dạng nhưng không có Config Name lẫn ID.")
        if p.has_id:
            ids[p.ad_id].append(p.row)
            if not formats.ADMOB_UNIT_ID.fullmatch(p.ad_id):
                warn("SPEC-ID-FORMAT", f"Dòng {p.row}: ID '{p.ad_id}' sai định dạng AdMob.")
            publisher = formats.publisher(p.ad_id)
            if publisher:
                publishers.add(publisher)
        if p.space_name:
            spaces[p.space_name].append(p.row)
        if formats.allowed_ads_types(p.format) is None:
            warn("SPEC-UNKNOWN-FORMAT", f"Dòng {p.row}: Định Dạng '{p.format}' chưa có trong bảng ánh xạ.")
        if p.space_name and p.network_name and p.network_name != "Am_" + p.space_name:
            findings.append(
                Finding(
                    "SPEC-NAME-MISMATCH",
                    Severity.INFO,
                    f"Dòng {p.row}: Ad Space '{p.space_name}' khác Network Ad Name '{p.network_name}' "
                    "(ngoài tiền tố Am_).",
                    (p.row,),
                )
            )
    for ad_id, rows in ids.items():
        if len(rows) > 1:
            findings.append(
                Finding(
                    "SPEC-DUP-ID", Severity.WARN, f"ID {ad_id} lặp ở dòng {', '.join(map(str, rows))}.", tuple(rows)
                )
            )
    for space, rows in spaces.items():
        if len(rows) > 1:
            findings.append(
                Finding(
                    "SPEC-DUP-SPACE",
                    Severity.WARN,
                    f"Ad Space '{space}' lặp ở dòng {', '.join(map(str, rows))}.",
                    tuple(rows),
                )
            )
    if len(publishers) > 1:
        findings.append(
            Finding(
                "SPEC-PUBLISHER", Severity.WARN, f"Spec có ID của nhiều publisher: {', '.join(sorted(publishers))}."
            )
        )
    return findings
