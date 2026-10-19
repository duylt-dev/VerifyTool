"""Placement configuration findings and state (static-check-spec §6.2)."""

from apkverify import formats
from apkverify.model import AdsConfig, AdUnitList, Finding, Placement, Severity, Spec
from apkverify.process.suggest import suggestion


def rc_config_state(p: Placement, config: AdsConfig | None) -> str:
    if not p.has_config:
        return "—"
    if config is not None:
        for c in config.configs:
            if c.config_name == p.config_name:
                return "BẬT" if c.is_on else "TẮT"
    return "THIẾU"


def check(spec: Spec, config: AdsConfig | None, lists: dict[str, AdUnitList]) -> list[Finding]:
    if config is None:
        return []
    findings = []
    groups: dict[str, list[Placement]] = {}
    for p in spec.placements:
        if p.has_config:
            groups.setdefault(p.config_name, []).append(p)
    names = [c.config_name for c in config.configs]
    for name, placements in groups.items():
        rows = tuple(p.row for p in placements)
        c = next((c for c in config.configs if c.config_name == name), None)
        if c is None:
            findings.append(
                Finding(
                    "RC-CONFIG-MISSING",
                    Severity.ERROR,
                    f"Thiếu config: '{name}' (dòng {', '.join(map(str, rows))}) không có trong config_show_ads; "
                    f'thư viện sẽ báo "ad config not found" và không show.{suggestion(name, names)}',
                    rows,
                )
            )
            continue
        if not c.is_on:
            findings.append(
                Finding("RC-CONFIG-OFF", Severity.WARN, f"Vị trí '{name}' đang TẮT (isOn=false): sẽ không show.", rows)
            )
        allowed = set().union(*(formats.allowed_ads_types(p.format) or set() for p in placements))
        if allowed and c.ads_type not in allowed:
            labels = ", ".join(f"'{label}'" for label in dict.fromkeys(p.format for p in placements))
            findings.append(
                Finding(
                    "RC-CONFIG-TYPE", Severity.WARN, f"Config '{name}' có type '{c.ads_type}', spec ghi {labels}.", rows
                )
            )
    for name in dict.fromkeys(names):
        if name not in groups:
            findings.append(
                Finding(
                    "RC-CONFIG-EXTRA",
                    Severity.WARN,
                    f"Thừa: config '{name}' có trên Remote Config nhưng không có trong spec.",
                )
            )
    if config.flag(formats.DISABLE_ALL_FLAG):
        findings.append(Finding("RC-DISABLE-ALL", Severity.WARN, "disableAllConfig = true: mọi quảng cáo bị tắt."))
    for ads_type, flag in formats.DISABLE_FLAG_BY_TYPE.items():
        if not config.flag(flag):
            continue
        spaces = {u.space_name for value in lists.values() for u in value.units if u.ads_type == ads_type}
        configs = {c.config_name for c in config.configs if c.ads_type == ads_type}
        rows = tuple(p.row for p in spec.placements if p.space_name in spaces or p.config_name in configs)
        if rows:
            findings.append(
                Finding("RC-DISABLE-TYPE", Severity.WARN, f"{flag} = true: các vị trí {ads_type} sẽ không show.", rows)
            )
    return findings
