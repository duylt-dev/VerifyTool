"""Load RC states and combine findings (static-check-spec §6.2)."""

from collections.abc import Sequence
from dataclasses import replace

from apkverify import formats
from apkverify.errors import RcFormatError
from apkverify.model import AdsConfig, AdUnitList, ApkFacts, Finding, RcValue, Severity, Spec
from apkverify.process.rc_parse import parse_ad_unit_list, parse_ads_config
from apkverify.process.static import rc_config_checks, rc_unit_checks
from apkverify.process.static.rc_config_checks import rc_config_state as rc_config_state
from apkverify.process.static.rc_unit_checks import rc_id_state as rc_id_state


def _missing(key: str) -> Finding:
    return Finding(
        "RC-KEY-MISSING",
        Severity.ERROR,
        f"Không có giá trị Remote Config '{key}' (thiếu trên Firebase hoặc chưa export vào input/).",
    )


def _invalid(key: str, error: RcFormatError) -> Finding:
    return Finding("RC-JSON-INVALID", Severity.ERROR, f"Giá trị Remote Config '{key}' không đọc được: {error}.")


def load_lists(rc_values: Sequence[RcValue]) -> tuple[dict[str, AdUnitList], list[Finding]]:
    values = {v.key: v.value for v in rc_values}
    lists = {}
    findings = []
    for key in formats.AD_UNIT_LIST_KEYS:
        text = values.get(key, "")
        if not text.strip():
            if key in formats.REQUIRED_KEYS:
                findings.append(_missing(key))
            continue
        try:
            lists[key] = parse_ad_unit_list(key, text)
        except RcFormatError as error:
            findings.append(_invalid(key, error))
    return lists, findings


def load_config(rc_values: Sequence[RcValue]) -> tuple[AdsConfig | None, list[Finding]]:
    text = next((v.value for v in rc_values if v.key == formats.ADS_CONFIG_KEY), "")
    if not text.strip():
        return None, [_missing(formats.ADS_CONFIG_KEY)]
    try:
        return parse_ads_config(text), []
    except RcFormatError as error:
        return None, [_invalid(formats.ADS_CONFIG_KEY, error)]


def check(spec: Spec, rc_values: Sequence[RcValue], apk: ApkFacts) -> list[Finding]:
    lists, list_findings = load_lists(rc_values)
    config, config_findings = load_config(rc_values)
    findings = []
    for finding in list_findings:
        rows = tuple(p.row for p in spec.placements if p.has_id) if "'admob_id'" in finding.message else ()
        findings.append(replace(finding, rows=rows))
    rows = tuple(p.row for p in spec.placements if p.has_config)
    findings.extend(replace(f, rows=rows) for f in config_findings)
    findings.extend(rc_unit_checks.check(spec, lists, apk))
    findings.extend(rc_config_checks.check(spec, config, lists))
    for value in rc_values:
        if value.key in formats.FALLBACK_KEYS and value.conditions:
            findings.append(
                Finding(
                    "RC-CONDITIONAL",
                    Severity.INFO,
                    f"'{value.key}' có giá trị theo điều kiện ({', '.join(value.conditions)}); "
                    "tool chỉ kiểm giá trị mặc định.",
                )
            )
    return findings
