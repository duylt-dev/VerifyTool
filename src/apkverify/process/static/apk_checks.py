"""Code, manifest and fallback findings (static-check-spec §6.3)."""

from apkverify import formats
from apkverify.errors import RcFormatError
from apkverify.model import ApkFacts, Finding, Placement, Severity, Spec
from apkverify.process.rc_parse import parse_ad_unit_list, parse_ads_config
from apkverify.process.suggest import suggestion


def code_space_state(p: Placement, apk: ApkFacts) -> str:
    return ("OK" if p.space_name in apk.dex_strings else "THIẾU") if p.has_id else "—"


def code_config_state(p: Placement, apk: ApkFacts) -> str:
    return ("OK" if p.config_name in apk.dex_strings else "THIẾU") if p.has_config else "—"


def _fallbacks(spec: Spec, apk: ApkFacts) -> list[Finding]:
    findings = []
    assets = {a.key: a for a in apk.fallbacks}
    for key in formats.FALLBACK_CHECKED_KEYS:
        asset = assets.get(key)
        if asset is None or not asset.present or not asset.text.strip():
            impact = (
                "nếu key admob_id trên Firebase rỗng, app không có ID quảng cáo nào."
                if key == formats.ADMOB_LIST_KEY
                else "nếu fetch Remote Config lỗi hoặc key rỗng, "
                "không vị trí nào có config nên không quảng cáo nào show."
            )
            findings.append(Finding("APK-FALLBACK-EMPTY", Severity.WARN, f"assets/{key}.txt rỗng: {impact}"))
            continue
        if key == formats.ADMOB_LIST_KEY:
            try:
                units = parse_ad_unit_list(key, asset.text).units
            except RcFormatError:
                units = ()
            affected = [
                p
                for p in spec.placements
                if p.has_id and not any(u.space_name == p.space_name and u.ad_id == p.ad_id for u in units)
            ]
            names = [p.space_name for p in affected]
        else:
            try:
                configs = {c.config_name for c in parse_ads_config(asset.text).configs}
            except RcFormatError:
                configs = set()
            affected = [p for p in spec.placements if p.has_config and p.config_name not in configs]
            names = [p.config_name for p in affected]
        if affected:
            findings.append(
                Finding(
                    "APK-FALLBACK-DIFF",
                    Severity.WARN,
                    f"assets/{key}.txt khác spec ở: {', '.join(dict.fromkeys(names))}.",
                    tuple(p.row for p in affected),
                )
            )
    return findings


def check(spec: Spec, apk: ApkFacts) -> list[Finding]:
    findings = []
    for key in formats.REQUIRED_KEYS:
        if key not in apk.dex_strings:
            findings.append(
                Finding(
                    "APK-LIB-KEYS",
                    Severity.ERROR,
                    f"Không thấy key Remote Config '{key}' trong code: APK không dùng thư viện quảng cáo mà tool biết, "
                    "kết quả kiểm tra không đáng tin.",
                )
            )
    if apk.admob_app_id is None:
        findings.append(
            Finding(
                "APK-NO-APPID",
                Severity.ERROR,
                "APK thiếu meta-data com.google.android.gms.ads.APPLICATION_ID: app sẽ crash khi khởi tạo AdMob.",
            )
        )
    elif formats.is_google_test_id(apk.admob_app_id):
        findings.append(
            Finding("APK-TEST-APPID", Severity.ERROR, f"APK đang dùng App ID test của Google ({apk.admob_app_id}).")
        )
    ids = sorted(s for s in apk.dex_strings if s.startswith(f"ca-app-pub-{formats.GOOGLE_TEST_PUBLISHER}/"))[:5]
    if ids:
        findings.append(Finding("APK-TEST-UNIT", Severity.WARN, f"Code chứa ID test của Google: {', '.join(ids)}."))
    candidates = [s for s in apk.dex_strings if len(s) <= 64]
    groups: dict[str, list[int]] = {}
    for p in spec.placements:
        if code_space_state(p, apk) == "THIẾU":
            findings.append(
                Finding(
                    "APK-SPACE-MISSING",
                    Severity.ERROR,
                    f"Code không gọi Ad Space '{p.space_name}' (dòng {p.row}): "
                    f"ID {p.ad_id} sẽ không bao giờ được request."
                    f"{suggestion(p.space_name, candidates)}",
                    (p.row,),
                )
            )
        if p.has_config:
            groups.setdefault(p.config_name, []).append(p.row)
    for name, rows in groups.items():
        if name not in apk.dex_strings:
            findings.append(
                Finding(
                    "APK-CONFIG-MISSING",
                    Severity.ERROR,
                    f"Code không gọi config '{name}' (dòng {', '.join(map(str, rows))}): vị trí này không có trong app."
                    f"{suggestion(name, candidates)}",
                    tuple(rows),
                )
            )
    return findings + _fallbacks(spec, apk)
