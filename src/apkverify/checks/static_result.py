"""Build a consistent finding list and per-placement table (§7)."""

from collections.abc import Sequence

from apkverify.checks import apk_checks, rc_checks, spec_lint
from apkverify.model import ApkFacts, PlacementStatus, RcValue, Severity, Spec, StaticResult


def build(spec: Spec, rc_values: Sequence[RcValue], apk: ApkFacts) -> StaticResult:
    findings = spec_lint.lint(spec) + rc_checks.check(spec, rc_values, apk) + apk_checks.check(spec, apk)
    findings.sort(key=lambda f: (-f.severity, f.code, f.rows[0] if f.rows else 0, f.message))
    lists, _ = rc_checks.load_lists(rc_values)
    config, _ = rc_checks.load_config(rc_values)
    statuses = []
    for p in spec.placements:
        severity = max((f.severity for f in findings if p.row in f.rows), default=Severity.INFO)
        verdict = "LỖI" if severity == Severity.ERROR else "CẢNH BÁO" if severity == Severity.WARN else "ĐẠT"
        statuses.append(
            PlacementStatus(
                p,
                rc_checks.rc_id_state(p, lists),
                rc_checks.rc_config_state(p, config),
                apk_checks.code_space_state(p, apk),
                apk_checks.code_config_state(p, apk),
                verdict,
            )
        )
    return StaticResult(spec, apk, tuple(rc_values), tuple(findings), tuple(statuses))
