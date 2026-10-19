"""DEX string-table decoding without androguard (static-check-spec §5)."""

import struct
from zipfile import ZipFile

import pytest
from conftest import MINI_APK

from apkverify.input.dex_strings import read_strings


def test_minimal_string_table() -> None:
    values = [b"hello", "Định dạng".encode(), b"x" * 130, b"bad\xff", b""]
    data = bytearray(0x70 + len(values) * 4)
    data[:8] = b"dex\n035\0"
    struct.pack_into("<II", data, 0x38, len(values), 0x70)
    for i, value in enumerate(values):
        struct.pack_into("<I", data, 0x70 + i * 4, len(data))
        data.extend(b"\x82\x01" if len(value) == 130 else bytes([len(value)]))
        data.extend(value + b"\0")
    assert read_strings(bytes(data)) == ["hello", "Định dạng", "x" * 130, "bad�", ""]


def test_real_fixture() -> None:
    with ZipFile(MINI_APK) as archive:
        strings = read_strings(archive.read("classes.dex"))
    assert {"admob_id", "config_show_ads", "home_bottom", "home_bottom_native", "Định dạng"} <= set(strings)
    assert "splash_interstitial" not in strings


@pytest.mark.parametrize("data", [b"", b"dex", b"zip\n", b"DEX\n035\0"])
def test_bad_magic(data: bytes) -> None:
    with pytest.raises(ValueError, match="^not a DEX file$"):
        read_strings(data)
