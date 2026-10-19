"""Value objects shared by readers, checks and reports (best-practices §9).

Everything here is frozen and holds tuples, so checks cannot mutate their inputs and values can cross threads.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Severity(enum.IntEnum):
    """Ordered so that `max()` gives the worst one (A8)."""

    INFO = 1
    WARN = 2
    ERROR = 3


@dataclass(frozen=True, slots=True)
class Finding:
    code: str  # stable code from a spec table, e.g. "RC-SPACE-MISSING"
    severity: Severity
    message: str  # Vietnamese, exactly the spec template filled in (A9)
    rows: tuple[int, ...] = ()  # Excel rows of the spec placements this finding concerns


# --- MO spec (static-check-spec §3) ---


@dataclass(frozen=True, slots=True)
class Placement:
    row: int  # Excel row number, 1-based
    group: str  # title of the enclosing group row ("Language", "Splash", ...)
    group_note: str  # "Ghi chú AD" of the group row
    task: str
    status: str  # "Trạng thái"
    format: str  # "Định Dạng" as written in the spec, e.g. "Native Full Screen"
    config_name: str  # "" when the row has none
    space_name: str
    network_name: str
    ad_id: str  # "" when the row has none
    note: str  # "Ghi chú AD" of this row
    task_code: str
    link: str

    @property
    def has_id(self) -> bool:
        return bool(self.ad_id)

    @property
    def has_config(self) -> bool:
        return bool(self.config_name)


@dataclass(frozen=True, slots=True)
class Spec:
    file_name: str
    sheet: str
    title: str  # first non-empty cell above the header row, "" if none
    placements: tuple[Placement, ...]


# --- Remote Config (static-check-spec §4) ---


@dataclass(frozen=True, slots=True)
class RcValue:
    key: str
    value: str  # "" when absent from the template, empty, or useInAppDefault
    source: str  # file name it came from
    conditions: tuple[str, ...] = ()  # names of conditional values in a template


@dataclass(frozen=True, slots=True)
class AdUnit:
    space_name: str
    ads_type: str
    ad_id: str
    buffer: int | None = None


@dataclass(frozen=True, slots=True)
class AdUnitList:
    """Parsed value of `admob_id`, `pangle_id` or `gam_id`."""

    key: str
    network: str
    app_id: str
    package: str
    units: tuple[AdUnit, ...]


@dataclass(frozen=True, slots=True)
class PlacementConfig:
    config_name: str
    is_on: bool
    ads_type: str


@dataclass(frozen=True, slots=True)
class AdsConfig:
    """Parsed value of `config_show_ads`."""

    flags: tuple[tuple[str, bool], ...]  # every top-level boolean whose name starts with "disable"
    configs: tuple[PlacementConfig, ...]

    def flag(self, name: str) -> bool:
        return dict(self.flags).get(name, False)


# --- APK (static-check-spec §5) ---


@dataclass(frozen=True, slots=True)
class FallbackAsset:
    key: str  # Remote Config key; the file is assets/<key>.txt
    present: bool
    text: str  # "" when absent or empty
    path: str = ""  # where the file is (project: "app/src/main/assets/admob_id.txt"); "" means assets/<key>.txt


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Where `ApkFacts` came from when `apkverify project` read an Android Studio project (static-check-spec §5.1)."""

    root: str  # absolute path of the project directory
    app_module: str  # Gradle path of the module that applies com.android.application, e.g. ":app"
    ad_library: str  # "group:artifact:version" of a known ad library dependency (formats.AD_LIBRARIES), "" if none
    source_files: int  # .kt/.java files whose string literals were read
    unresolved: tuple[tuple[str, str], ...]  # (fact, what the project says), for "package" and "admob_app_id"


@dataclass(frozen=True, slots=True)
class ApkFacts:
    """What the checks know about the build: read from an APK, or from a project when `project` is set."""

    file_name: str  # APK file name; project directory name
    sha256: str  # "" for a project
    size: int  # 0 for a project
    package: str  # "" when a project's applicationId is not a literal
    version_name: str
    version_code: str
    admob_app_id: str | None  # resolved value of meta-data com.google.android.gms.ads.APPLICATION_ID
    firebase_project_id: str | None
    firebase_app_id: str | None
    firebase_sender_id: str | None
    fallbacks: tuple[FallbackAsset, ...]
    dex_strings: frozenset[str]  # DEX string table; for a project, the string literals of its .kt/.java files
    project: ProjectInfo | None = None

    @property
    def label(self) -> str:
        """How messages name the build: "APK" or "project"."""
        return "APK" if self.project is None else "project"

    def known(self, fact: str) -> bool:
        """False when the project reader could not resolve `fact` ("package", "admob_app_id")."""
        return self.project is None or all(name != fact for name, _ in self.project.unresolved)


# --- Static result (static-check-spec §7, §8) ---


@dataclass(frozen=True, slots=True)
class PlacementStatus:
    placement: Placement
    rc_id: str  # "OK", "THIẾU", "SAI", "RỖNG", "TEST", "—"
    rc_config: str  # "BẬT", "TẮT", "THIẾU", "—"
    code_space: str  # "OK", "THIẾU", "—"
    code_config: str  # "OK", "THIẾU", "—"
    verdict: str  # "LỖI", "CẢNH BÁO", "ĐẠT"


@dataclass(frozen=True, slots=True)
class StaticResult:
    spec: Spec
    apk: ApkFacts
    rc_values: tuple[RcValue, ...]
    findings: tuple[Finding, ...]  # sorted: severity descending, then code, then first row
    statuses: tuple[PlacementStatus, ...]  # spec order

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def passed(self) -> bool:
        return self.count(Severity.ERROR) == 0


# --- Runtime (runtime-check-spec) ---


@dataclass(frozen=True, slots=True)
class AdEvent:
    """One parsed log line (runtime-check-spec §4)."""

    time: float  # epoch seconds from `logcat -v epoch`
    event: str  # "start load", "load success", ..., "screen", "fetch-ok", "fetch-failed"
    source: str  # text between the event and ":" (AdClass, adsType, "Interstitial Preload"); screen id for "screen"
    names: tuple[str, ...]  # name tokens (config and/or space names)
    ad_unit: str  # "" when the line has none
    code: str  # error code of a failed event, "" otherwise
    message: str  # error text of a failed event, "" otherwise
    structured: bool  # True when the line had an ad unit token; only these feed RT-EXTRA


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    serial: str
    model: str
    android: str  # ro.build.version.release
    emulator: bool


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    placement: Placement
    status: str  # "ĐÃ SHOW", "ĐÃ LOAD", "LỖI", "ĐÃ REQUEST", "CHƯA THẤY"
    shows: int
    first_time: float | None
    last_time: float | None
    errors: tuple[str, ...]  # "<code> <message>" of failed events, distinct, in order
    verdict: str  # "LỖI", "CẢNH BÁO", "ĐẠT"


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    spec: Spec
    apk: ApkFacts
    device: DeviceInfo
    started: float  # epoch seconds
    ended: float
    events: tuple[AdEvent, ...]
    findings: tuple[Finding, ...]  # sorted like StaticResult.findings
    statuses: tuple[RuntimeStatus, ...]  # spec order
    log_file: str  # name of the raw log written next to the report

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def passed(self) -> bool:
        return self.count(Severity.ERROR) == 0
