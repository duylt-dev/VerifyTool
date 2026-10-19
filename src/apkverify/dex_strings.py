"""Read only the DEX string table (static-check-spec §5)."""

import struct


def read_strings(dex: bytes) -> list[str]:
    if dex[:4] != b"dex\n":
        raise ValueError("not a DEX file")
    count, offset = struct.unpack_from("<II", dex, 0x38)
    strings = []
    for i in range(count):
        (position,) = struct.unpack_from("<I", dex, offset + 4 * i)
        while dex[position] >= 0x80:
            position += 1
        position += 1
        end = dex.index(0, position)
        strings.append(dex[position:end].decode("utf-8", errors="replace"))
    return strings
