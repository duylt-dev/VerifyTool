"""Pure helpers use observed adb output; executable discovery does not spawn adb (§2)."""

import os
from pathlib import Path

import pytest

from apkverify.errors import AdbError
from apkverify.runtime.adb import find_adb, install_failure, parse_devices


@pytest.mark.parametrize(
    "text,expected",
    [
        ("List of devices attached\nemulator-5554\tdevice\n", [("emulator-5554", "device")]),
        (
            "List of devices attached\n"
            "emulator-5554 device product:sdk model:sdk_gphone16k_arm64 device:emu transport_id:1\n",
            [("emulator-5554", "device")],
        ),
        ("List of devices attached\n\n", []),
        (
            "* daemon started successfully\nList of devices attached\na\toffline\nb\tunauthorized\nc\tdevice\n",
            [("a", "offline"), ("b", "unauthorized"), ("c", "device")],
        ),
    ],
)
def test_parse_devices(text: str, expected: list[tuple[str, str]]) -> None:
    assert parse_devices(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Performing Streamed Install\nSuccess\n", None),
        (
            "Performing Streamed Install\nFailure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures differ]\n",
            "INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures differ",
        ),
        ("Failure [INSTALL_FAILED_INVALID_APK: invalid]\n", "INSTALL_FAILED_INVALID_APK: invalid"),
        ("Failure [old error]\nSuccess\n", None),
    ],
)
def test_install_failure(text: str, expected: str | None) -> None:
    assert install_failure(text) == expected


@pytest.mark.parametrize("variable", ["ANDROID_HOME", "ANDROID_SDK_ROOT"])
def test_find_adb_sdk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variable: str) -> None:
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    executable = tmp_path / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    executable.parent.mkdir()
    executable.write_text("", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv(variable, str(tmp_path))
    assert find_adb() == str(executable)


def test_find_adb_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("ANDROID_HOME", raising=False)
    monkeypatch.delenv("ANDROID_SDK_ROOT", raising=False)
    with pytest.raises(AdbError, match=r"PATH, \$ANDROID_HOME/platform-tools.*\$ANDROID_SDK_ROOT/platform-tools"):
        find_adb()
