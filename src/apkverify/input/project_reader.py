"""Android Studio project → ApkFacts, so the static checks run on source (static-check-spec §5.1)."""

import json
import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from apkverify import formats
from apkverify.errors import InputError
from apkverify.input import project_text
from apkverify.input.source_strings import literals, strip_comments
from apkverify.model import ApkFacts, FallbackAsset, ProjectInfo

log = logging.getLogger(__name__)

SETTINGS = ("settings.gradle.kts", "settings.gradle")
BUILD_FILES = ("build.gradle.kts", "build.gradle")
SOURCE_SUFFIXES = (".kt", ".java")
LAST_INPUTS = "last-inputs.json"
T = TypeVar("T")


def find_project(start: Path) -> Path:
    """The nearest directory, from `start` upwards, that holds a Gradle settings file."""
    start = start.expanduser().resolve()
    for directory in (start, *start.parents):
        if any((directory / name).is_file() for name in SETTINGS):
            return directory
    raise InputError(
        f"Không thấy project Android: không có settings.gradle(.kts) trong {start} hay thư mục cha. "
        "Mở Terminal ở thư mục project trong Android Studio, hoặc chỉ rõ --project DIR."
    )


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as error:
        raise InputError(f"Không đọc được {path}: {error}.") from error


def _gradle(directory: Path, names: tuple[str, ...]) -> tuple[Path | None, str]:
    for name in names:
        path = directory / name
        if path.is_file():
            return path, strip_comments(_read(path), path.suffix)
    return None, ""


def _release_source_set(name: str) -> bool:
    """Source sets that can reach a release build: not tests (`test*`, `androidTest*`, `*Test`), not debug."""
    tests = name.startswith(("test", "androidTest")) or name.endswith("Test")
    return not tests and name != "debug" and not name.endswith("Debug")


def _release_sets(module: Path) -> list[Path]:
    """`<module>/src/<set>` that can reach a release build, `main` first."""
    source = module / "src"
    if not source.is_dir():
        return []
    sets = sorted(p for p in source.iterdir() if p.is_dir() and _release_source_set(p.name))
    return sorted(sets, key=lambda path: path.name != "main")


def _source_strings(modules: list[Path]) -> tuple[frozenset[str], int]:
    strings: set[str] = set()
    count = 0
    for module in modules:
        for source_set in _release_sets(module):
            for path in sorted(source_set.rglob("*")):
                if path.suffix in SOURCE_SUFFIXES and path.is_file():
                    strings.update(literals(_read(path), path.suffix))
                    count += 1
    return frozenset(strings), count


def _xml(path: Path, parse: Callable[[str], T]) -> T:
    try:
        return parse(_read(path))
    except ET.ParseError as error:
        raise InputError(f"File XML không hợp lệ {path}: {error}.") from error


def _app_id(root: Path, modules: list[Path]) -> tuple[str | None, str]:
    """(AdMob App ID, why it is unresolved or ""), from the manifests of every release source set, `main` first.

    A value declared only outside `main`, or one that differs between source sets, depends on the variant built.
    """
    sets = [source_set for module in modules for source_set in _release_sets(module)]
    found = [
        (manifest, value)
        for manifest in (source_set / "AndroidManifest.xml" for source_set in sets)
        if manifest.is_file() and (value := _xml(manifest, project_text.manifest_app_id)) is not None
    ]
    if not found:
        return None, ""
    manifest, value = found[0]
    if manifest.parent.name != "main":
        return value, f"{value} chỉ khai báo trong {manifest.relative_to(root).as_posix()}"
    if len({value for _, value in found}) > 1:
        return value, f"{value} khác nhau giữa các source set"
    if value.startswith("${"):
        return value, value
    if not value.startswith("@string/"):
        return value, ""
    name = value.removeprefix("@string/")
    values = [
        strings[name]
        for source_set in sets
        for path in sorted((source_set / "res/values").glob("*.xml"))
        if name in (strings := _xml(path, project_text.string_resources))
    ]
    if not values:
        return value, value
    if len(set(values)) > 1:
        return values[0], f"{value} khác nhau giữa các source set"
    return values[0], ""


def _firebase(app: Path, package: str) -> tuple[str | None, str | None, str | None]:
    for path in (app / "google-services.json", *(s / "google-services.json" for s in _release_sets(app))):
        if path.is_file():
            try:
                return project_text.firebase_ids(_read(path), package)
            except (ValueError, AttributeError, TypeError) as error:
                log.warning("google-services.json không đọc được: %s", error)
    return None, None, None


def _fallbacks(root: Path, modules: list[Path]) -> tuple[FallbackAsset, ...]:
    assets = []
    for key in formats.FALLBACK_KEYS:
        candidates = [module / "src/main/assets" / f"{key}.txt" for module in modules]
        found = next((path for path in candidates if path.is_file()), None)
        text = _read(found) if found else ""
        assets.append(
            FallbackAsset(key, found is not None, text, (found or candidates[0]).relative_to(root).as_posix())
        )
    return tuple(assets)


def read_project(root: Path) -> ApkFacts:
    settings_path, settings = _gradle(root, SETTINGS)
    names = project_text.included_modules(settings) or [":app"]
    modules = {name: root / name.strip(":").replace(":", "/") for name in names}
    builds = {name: _gradle(path, BUILD_FILES) for name, path in modules.items() if path.is_dir()}
    app_name = next((name for name, (_, text) in builds.items() if project_text.is_application(text)), None)
    if app_name is None:
        raise InputError(f"Không thấy module ứng dụng (plugin com.android.application) trong {settings_path}.")
    order = [modules[app_name], *(modules[name] for name in builds if name != app_name)]
    app_build_path, app_build = builds[app_name]
    build_name = app_build_path.relative_to(root).as_posix()
    unresolved = []
    package, expression = project_text.application_id(app_build)
    if package is None:
        unresolved.append(("package", expression or f"không có dòng applicationId trong {build_name}"))
    version_name, _ = project_text.gradle_value(app_build, "versionName")
    version_code, _ = project_text.gradle_value(app_build, "versionCode")
    app_id, why = _app_id(root, order)
    if why:
        unresolved.append(("admob_app_id", why))
    catalog = root / "gradle/libs.versions.toml"
    declared = "\n".join(text for _, text in builds.values())
    if catalog.is_file():
        declared += "\n" + "\n".join(line for line in _read(catalog).splitlines() if not line.lstrip().startswith("#"))
    strings, count = _source_strings(order)
    return ApkFacts(
        root.name,
        "",
        0,
        package or "",
        version_name or "",
        version_code or "",
        app_id,
        *_firebase(modules[app_name], package or ""),
        _fallbacks(root, order),
        strings,
        ProjectInfo(str(root), app_name, project_text.ad_library(declared), count, tuple(unresolved)),
    )


def read_last_inputs(out_dir: Path) -> dict[str, Path]:
    """Answers of the previous `apkverify project` run whose files still exist; {} when there is none."""
    try:
        data = json.loads((out_dir / LAST_INPUTS).read_text(encoding="utf-8"))
        return {key: Path(value) for key, value in data.items() if Path(value).is_file()}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}
