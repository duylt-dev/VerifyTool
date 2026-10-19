"""Manifest/resources via androguard; DEX and fallback assets via zipfile (§5)."""

import hashlib
import re
from pathlib import Path
from zipfile import ZipFile

from androguard.core.apk import APK
from loguru import logger

from apkverify import formats
from apkverify.dex_strings import read_strings
from apkverify.errors import ApkError
from apkverify.model import ApkFacts, FallbackAsset

logger.remove()

ANDROID = "{http://schemas.android.com/apk/res/android}"


def _resolve(resources: object, resource_id: int) -> str | None:
    if resources is None:
        return None
    values = resources.get_resolved_res_configs(resource_id)
    return values[0][1] if values else None


def _app_id(apk: APK) -> str | None:
    for element in apk.get_android_manifest_xml().iter("meta-data"):
        if element.get(f"{ANDROID}name") == formats.ADMOB_APP_ID_META:
            value = element.get(f"{ANDROID}value")
            if value and value.startswith("@"):
                try:
                    return _resolve(apk.get_android_resources(), int(value[1:], 16)) or value
                except Exception:
                    return value
            return value
    return None


def _string(apk: APK, name: str) -> str | None:
    resources = apk.get_android_resources()
    if resources is not None:
        for package in resources.get_packages_names():
            resource_id = resources.get_res_id_by_key(package, "string", name)
            if resource_id is not None:
                value = _resolve(resources, resource_id)
                if value is not None:
                    return value
    return None


def read_apk(path: Path) -> ApkFacts:
    try:
        apk = APK(str(path))
        if not apk.is_valid_APK():
            raise ValueError("manifest không hợp lệ")
        strings: set[str] = set()
        fallbacks = []
        with ZipFile(path) as archive:
            for name in archive.namelist():
                if re.fullmatch(r"classes\d*\.dex", name):
                    strings.update(read_strings(archive.read(name)))
            for key in formats.FALLBACK_KEYS:
                name = f"assets/{key}.txt"
                present = name in archive.namelist()
                text = archive.read(name).decode("utf-8-sig", errors="replace") if present else ""
                fallbacks.append(FallbackAsset(key, present, text))
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return ApkFacts(
            path.name,
            digest.hexdigest(),
            path.stat().st_size,
            apk.get_package(),
            apk.get_androidversion_name() or "",
            apk.get_androidversion_code() or "",
            _app_id(apk),
            _string(apk, "project_id"),
            _string(apk, "google_app_id"),
            _string(apk, "gcm_defaultSenderId"),
            tuple(fallbacks),
            frozenset(strings),
        )
    except Exception as error:
        raise ApkError(f"Không đọc được APK {path.name}: {error}.") from error
