"""Ad unit list findings and state (static-check-spec §6.2)."""

from collections import Counter

from apkverify import formats
from apkverify.model import AdUnitList, ApkFacts, Finding, Placement, Severity, Spec
from apkverify.suggest import suggestion


def rc_id_state(p: Placement, lists: dict[str, AdUnitList]) -> str:
    if not p.has_id:
        return "—"
    units = [u for value in lists.values() for u in value.units if u.space_name == p.space_name]
    if formats.ADMOB_LIST_KEY not in lists or not units:
        return "THIẾU"
    if all(not u.ad_id for u in units):
        return "RỖNG"
    if any(formats.is_google_test_id(u.ad_id) for u in units):
        return "TEST"
    return "OK" if any(u.ad_id == p.ad_id for u in units) else "SAI"


def check(spec: Spec, lists: dict[str, AdUnitList], apk: ApkFacts) -> list[Finding]:
    findings = []
    units = [(key, u) for key, value in lists.items() for u in value.units]
    names = [u.space_name for _, u in units]
    for p in spec.placements:
        matches = [(key, u) for key, u in units if u.space_name == p.space_name]
        state = rc_id_state(p, lists)
        if state == "THIẾU" and formats.ADMOB_LIST_KEY in lists:
            findings.append(
                Finding(
                    "RC-SPACE-MISSING",
                    Severity.ERROR,
                    f"Thiếu ID: Ad Space '{p.space_name}' (dòng {p.row}) không có trong '{', '.join(lists)}'."
                    f"{suggestion(p.space_name, names)}",
                    (p.row,),
                )
            )
        elif state == "SAI":
            found = ", ".join(u.ad_id for _, u in matches)
            findings.append(
                Finding(
                    "RC-ID-MISMATCH",
                    Severity.ERROR,
                    f"Sai ID: '{p.space_name}' trên Remote Config là {found}, spec là {p.ad_id}.",
                    (p.row,),
                )
            )
        elif state == "RỖNG":
            findings.append(
                Finding(
                    "RC-ID-EMPTY",
                    Severity.ERROR,
                    f"ID rỗng: '{p.space_name}' có trong '{matches[0][0]}' nhưng id rỗng, thư viện sẽ bỏ qua.",
                    (p.row,),
                )
            )
        allowed = formats.allowed_ads_types(p.format)
        for _, unit in matches:
            if allowed and unit.ads_type not in allowed:
                findings.append(
                    Finding(
                        "RC-TYPE-MISMATCH",
                        Severity.WARN,
                        f"'{p.space_name}': adsType '{unit.ads_type}' không khớp Định Dạng '{p.format}' của spec.",
                        (p.row,),
                    )
                )
    for key, value in lists.items():
        if formats.is_google_test_id(value.app_id):
            findings.append(
                Finding("RC-ID-TEST", Severity.ERROR, f"'{key}.appId' đang dùng ID test của Google ({value.app_id}).")
            )
        for unit in value.units:
            rows = tuple(p.row for p in spec.placements if p.space_name == unit.space_name)
            if formats.is_google_test_id(unit.ad_id):
                findings.append(
                    Finding(
                        "RC-ID-TEST",
                        Severity.ERROR,
                        f"'{unit.space_name}' đang dùng ID test của Google ({unit.ad_id}).",
                        rows,
                    )
                )
            if key == formats.ADMOB_LIST_KEY:
                if unit.ad_id and not formats.ADMOB_UNIT_ID.fullmatch(unit.ad_id):
                    findings.append(
                        Finding(
                            "RC-ID-FORMAT",
                            Severity.ERROR,
                            f"'{unit.space_name}': ID '{unit.ad_id}' sai định dạng AdMob.",
                            rows,
                        )
                    )
                pub, app_pub = formats.publisher(unit.ad_id), formats.publisher(value.app_id)
                if pub and app_pub and pub != app_pub:
                    findings.append(
                        Finding(
                            "RC-PUBLISHER",
                            Severity.ERROR,
                            f"'{unit.space_name}': ID thuộc publisher {pub}, App ID thuộc {app_pub}.",
                            rows,
                        )
                    )
    for name, count in Counter(names).items():
        rows = tuple(p.row for p in spec.placements if p.space_name == name)
        if not rows:
            findings.append(
                Finding(
                    "RC-SPACE-EXTRA",
                    Severity.WARN,
                    f"Thừa: Ad Space '{name}' có trên Remote Config nhưng không có trong spec.",
                )
            )
        if count > 1:
            findings.append(
                Finding(
                    "RC-DUP-SPACE", Severity.WARN, f"Ad Space '{name}' xuất hiện {count} lần trên Remote Config.", rows
                )
            )
    admob = lists.get(formats.ADMOB_LIST_KEY)
    if admob:
        if admob.app_id != apk.admob_app_id:
            findings.append(
                Finding(
                    "RC-APPID-MISMATCH",
                    Severity.ERROR,
                    f"App ID trên Remote Config ({admob.app_id}) khác App ID trong APK ({apk.admob_app_id}).",
                )
            )
        if admob.package != apk.package:
            findings.append(
                Finding(
                    "RC-PACKAGE-MISMATCH",
                    Severity.ERROR,
                    f"Package trên Remote Config ({admob.package}) khác package APK ({apk.package}).",
                )
            )
    return findings
