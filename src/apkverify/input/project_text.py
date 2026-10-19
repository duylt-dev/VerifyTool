"""Pure: values from the text of Gradle, manifest, resource and google-services files (static-check-spec §5.1).

Gradle files are programs; this reads only literals written the way Android Studio writes them, and returns None
when a value is computed, so the caller can report it instead of guessing. Pass Gradle text through
`source_strings.strip_comments` first: a commented-out `include(":old")` must not count.
"""

import json
import re
import xml.etree.ElementTree as ET

from apkverify import formats

ANDROID_NAME = "{http://schemas.android.com/apk/res/android}name"
ANDROID_VALUE = "{http://schemas.android.com/apk/res/android}value"


_QUOTED = r"""["'][^"'\n]+["']"""


def included_modules(settings: str) -> list[str]:
    """Gradle paths from `include(":app")`, `include ':a', ':b'`, over several lines too; `includeBuild` is not one."""
    modules: list[str] = []
    for match in re.finditer(rf"\binclude\b[ \t]*\(?\s*((?:{_QUOTED}\s*,\s*)*{_QUOTED})", settings):
        modules += re.findall(r"""["']:?([\w.\-:]+)["']""", match.group(1))
    return list(dict.fromkeys(f":{name}" for name in modules))


def is_application(build: str) -> bool:
    """The build file applies the Android application plugin (by id, or by a version-catalog alias)."""
    return re.search(r"com\.android\.application|\bandroid[.\-]application\b", build) is not None


def _assignments(build: str, name: str) -> list[re.Match[str]]:
    """Lines `name = x` / `name x`; group 1 is the expression."""
    return list(re.finditer(rf"^[ \t]*{name}\b[ \t]*=?[ \t]*(.*?)[ \t]*$", build, re.MULTILINE))


def _literal(expression: str) -> str | None:
    literal = re.fullmatch(r"""(["'])([^"'$]*)\1|(\d+)""", expression)
    if literal is None:
        return None
    return literal.group(2) if literal.group(2) is not None else literal.group(3)


def gradle_value(build: str, name: str) -> tuple[str | None, str]:
    """(literal, expression) of the first line `name = "x"`, `name "x"` or `name = 7`; literal None if computed."""
    matches = _assignments(build, name)
    if not matches:
        return None, ""
    expression = matches[0].group(1)
    return _literal(expression), expression


def _block(build: str, position: int) -> str:
    """The line that opens the `{ … }` block around `position`, e.g. `create("free") {`; "" at top level."""
    depth = 0
    for i in range(position - 1, -1, -1):
        if build[i] == "}":
            depth += 1
        elif build[i] == "{":
            if depth == 0:
                return build[build.rfind("\n", 0, i) + 1 : i].strip()
            depth -= 1
    return ""


def application_id(build: str) -> tuple[str | None, str]:
    """(package, expression) of the app module; package None when flavors or build types can change it.

    Every `applicationId` must be the same literal, and no `applicationIdSuffix` may apply outside a debug block:
    otherwise the tool cannot know which package the shipped variant has.
    """
    matches = _assignments(build, "applicationId")
    if not matches:
        return None, ""
    expressions = [match.group(1) for match in matches]
    values = {_literal(expression) for expression in expressions}
    if None in values:
        return None, next(e for e in expressions if _literal(e) is None)
    if len(values) > 1:
        return None, "applicationId khác nhau theo flavor: " + ", ".join(sorted(values))
    for suffix in _assignments(build, "applicationIdSuffix"):
        block = _block(build, suffix.start())
        if "debug" not in block.casefold():
            return None, f"applicationIdSuffix {suffix.group(1)} trong {block or 'android'}"
    return values.pop(), expressions[0]


def ad_library(text: str) -> str:
    """The first known ad library (formats.AD_LIBRARIES) declared in a build file or version catalog, else ""."""
    for library in formats.AD_LIBRARIES:
        group, artifact = library.split(":")
        match = re.search(rf"""["']({re.escape(library)}(?::[^"'\s]+)?)["']""", text)
        if match:
            return match.group(1)
        group_part = rf"""group\s*[:=]\s*["']{re.escape(group)}["']"""
        name_part = rf"""name\s*[:=]\s*["']{re.escape(artifact)}["']"""
        if re.search(rf"{group_part}\s*,\s*{name_part}|{name_part}\s*,\s*{group_part}", text):
            return library
    return ""


def manifest_app_id(manifest: str) -> str | None:
    """android:value of the AdMob APPLICATION_ID meta-data, None when the manifest has none."""
    for element in ET.fromstring(manifest).iter("meta-data"):
        if element.get(ANDROID_NAME) == formats.ADMOB_APP_ID_META:
            return element.get(ANDROID_VALUE, "")
    return None


def string_resources(values_xml: str) -> dict[str, str]:
    """`<string name="x">value</string>` of a res/values file; Android's surrounding quotes and \\' are undone."""
    strings = {}
    for element in ET.fromstring(values_xml).iter("string"):
        value = "".join(element.itertext()).strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        strings[element.get("name", "")] = value.replace("\\'", "'")
    return strings


def firebase_ids(google_services: str, package: str) -> tuple[str | None, str | None, str | None]:
    """(project_id, mobilesdk_app_id of `package`'s client, project_number) from google-services.json."""
    data = json.loads(google_services)
    info = data.get("project_info", {})
    app_id = next(
        (
            client.get("client_info", {}).get("mobilesdk_app_id")
            for client in data.get("client", [])
            if client.get("client_info", {}).get("android_client_info", {}).get("package_name") == package
        ),
        None,
    )
    return info.get("project_id"), app_id, info.get("project_number")
