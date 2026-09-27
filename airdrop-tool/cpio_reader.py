"""Minimal reader for the "newc" (SVR4 no-CRC) cpio format.

AirDrop's /Upload request body is a cpio archive containing every file
(and directory) being sent, back to back. This avoids pulling in an
external cpio binary/library for such a small, well-documented format.
"""
from dataclasses import dataclass

_HEADER_SIZE = 110
_MAGIC = b"070701"
_TRAILER_NAME = "TRAILER!!!"


@dataclass
class CpioEntry:
    name: str
    mode: int
    is_directory: bool
    data: bytes


def _pad4(n: int) -> int:
    return (4 - n % 4) % 4


def read_entries(archive: bytes) -> list[CpioEntry]:
    entries: list[CpioEntry] = []
    offset = 0
    total = len(archive)

    while offset + _HEADER_SIZE <= total:
        header = archive[offset : offset + _HEADER_SIZE]
        magic = header[0:6]
        if magic != _MAGIC:
            raise ValueError(f"Unexpected cpio magic {magic!r} at offset {offset}")

        def field(start: int) -> int:
            return int(header[start : start + 8], 16)

        mode = field(14)
        filesize = field(54)
        namesize = field(94)

        name_start = offset + _HEADER_SIZE
        name_end = name_start + namesize
        name = archive[name_start : name_end - 1].decode("utf-8", "replace")  # strip trailing NUL

        data_start = name_end + _pad4(name_end)
        data_end = data_start + filesize
        data = archive[data_start:data_end]

        offset = data_end + _pad4(data_end)

        if name == _TRAILER_NAME:
            break

        is_directory = (mode & 0o170000) == 0o040000
        entries.append(CpioEntry(name=name, mode=mode, is_directory=is_directory, data=data))

    return entries
