"""Parse the ad library's epoch logcat lines (runtime-check-spec §3–§4)."""

import re

from apkverify.model import AdEvent

_LINE = re.compile(r"^\s*(\d+\.\d+)\s+\d+\s+\d+\s+([VDIWEF])\s+([^:]+?)\s*: (.*)$")
_EVENT = re.compile(
    r"^(banner refresh failed|banner refresh|onAdsExhausted|load success|show success|"
    r"start load|load failed|show failed|got reward|clicked|click|close) ([^:]+): (.*)$"
)


def parse_line(line: str) -> AdEvent | None:
    match = _LINE.match(line.rstrip("\r\n"))
    if not match:
        return None
    timestamp, _, tag, message = match.groups()
    time = float(timestamp)
    if tag == "CHECKINITADS":
        for value, event in (("false", "fetch-failed"), ("true", "fetch-ok")):
            if f"isSuccessful = {value}" in message:
                return AdEvent(time, event, "", (), "", "", "", False)
        return None
    if tag != "TESTERADSEVENT" or not message.strip():
        return None
    if message.startswith("Screen change to: "):
        return AdEvent(time, "screen", message.removeprefix("Screen change to: "), (), "", "", "", False)
    match = _EVENT.match(message)
    if not match:
        return None
    event, source, rest = match.groups()
    tokens = rest.split()
    unit_index = next((i for i, token in enumerate(tokens) if token.startswith("ca-app-pub-")), None)
    code = error = ad_unit = ""
    if unit_index is not None:
        names = tuple(tokens[:unit_index])
        ad_unit = tokens[unit_index]
        tail = tokens[unit_index + 1 :]
        if "failed" in event:
            code_index = next((i for i, token in enumerate(tail) if token.isdigit()), None)
            if code_index is not None:
                code, error = tail[code_index], " ".join(tail[code_index + 1 :])
    else:
        code_index = next((i for i, token in enumerate(tokens) if token.isdigit()), len(tokens))
        names = tuple(tokens[: min(code_index, 1)]) or (source,)
        if code_index < len(tokens):
            code, error = tokens[code_index], " ".join(tokens[code_index + 1 :])
        else:
            error = " ".join(tokens[1:])
    return AdEvent(time, event, source, names, ad_unit, code, error, unit_index is not None)
