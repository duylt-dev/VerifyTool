"""Remote Config file reader (static-check-spec §4). Values are parsed later by `process/rc_parse.py`."""

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from apkverify.errors import InputError
from apkverify.model import RcValue


def _entries(path: Path, key: str) -> tuple[list[RcValue], bool]:
    """Values in one file and whether it is a Firebase template; a single-parameter file holds `key`."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise InputError(f"Không đọc được file Remote Config {path.name}: {error}.") from error
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if not (isinstance(data, dict) and ("parameters" in data or "parameterGroups" in data)):
        return [RcValue(key, text, path.name)], False
    parameters = list(data.get("parameters", {}).items())
    for group in data.get("parameterGroups", {}).values():
        parameters.extend(group.get("parameters", {}).items())
    entries = []
    for name, parameter in parameters:
        default = parameter.get("defaultValue", {})
        value = "" if default.get("useInAppDefault") else default.get("value", "")
        entries.append(RcValue(name, value, path.name, tuple(parameter.get("conditionalValues", {}))))
    return entries, True


def _merge(files: Iterable[list[RcValue]]) -> tuple[RcValue, ...]:
    values: dict[str, RcValue] = {}
    for entries in files:
        for entry in entries:
            if entry.key in values:
                raise InputError(
                    f"Key Remote Config '{entry.key}' có ở hai file: {values[entry.key].source}, {entry.source}."
                )
            values[entry.key] = entry
    return tuple(values[k] for k in sorted(values))


def read_rc_files(paths: Sequence[Path]) -> tuple[RcValue, ...]:
    """Discovered files: a single-parameter file's key is its stem (`admob_id.json` → `admob_id`)."""
    return _merge(_entries(path, path.stem)[0] for path in paths)


def read_rc_answers(answers: Sequence[tuple[str, Path]]) -> tuple[RcValue, ...]:
    """Files named by the key they were asked for (`apkverify project`); one template may answer several keys."""
    files, templates = [], set()
    for key, path in answers:
        if path.resolve() in templates:
            continue
        entries, template = _entries(path, key)
        if template:
            templates.add(path.resolve())
        files.append(entries)
    return _merge(files)
