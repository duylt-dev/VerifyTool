"""Remote Config file reader (static-check-spec §4). Values are parsed later by `process/rc_parse.py`."""

import json
from collections.abc import Sequence
from pathlib import Path

from apkverify.errors import InputError
from apkverify.model import RcValue


def read_rc_files(paths: Sequence[Path]) -> tuple[RcValue, ...]:
    values: dict[str, RcValue] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as error:
            raise InputError(f"Không đọc được file Remote Config {path.name}: {error}.") from error
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        entries = []
        if isinstance(data, dict) and ("parameters" in data or "parameterGroups" in data):
            parameters = list(data.get("parameters", {}).items())
            for group in data.get("parameterGroups", {}).values():
                parameters.extend(group.get("parameters", {}).items())
            for key, parameter in parameters:
                default = parameter.get("defaultValue", {})
                value = "" if default.get("useInAppDefault") else default.get("value", "")
                entries.append(RcValue(key, value, path.name, tuple(parameter.get("conditionalValues", {}))))
        else:
            entries.append(RcValue(path.stem, text, path.name))
        for entry in entries:
            if entry.key in values:
                raise InputError(
                    f"Key Remote Config '{entry.key}' có ở hai file: {values[entry.key].source}, {path.name}."
                )
            values[entry.key] = entry
    return tuple(values[k] for k in sorted(values))
