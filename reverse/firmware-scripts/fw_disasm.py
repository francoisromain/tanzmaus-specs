#!/usr/bin/env python3
"""Disassemble a decoded Tanzmaus firmware image (Thumb-2, base 0x08000000).

Usage:
  fw_disasm.py <image.bin> <image_offset> <length>
      Disassemble `length` bytes of Thumb code starting at `image_offset`.

  fw_disasm.py <image.bin> --start=<addr> --end=<addr>
      Disassemble the flash range [addr, end) (addresses in the 0x08000000 space).

Image offsets are relative to the decoded .bin; flash addresses are absolute.
The base is FLASH_BASE = 0x08000000.
"""
from __future__ import annotations

import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_OPT_DETAIL

FLASH_BASE = 0x08000000


def load(path: Path) -> bytes:
    return path.read_bytes()


def disasm(data: bytes, offset: int, length: int, abs_base: int = 0):
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    md.detail = True
    code = data[offset:offset + length]
    for insn in md.disasm(code, abs_base + offset):
        yield insn


def main(argv):
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2

    img = Path(argv[1])
    data = load(img)

    if argv[2].startswith("--start="):
        start = int(argv[2].split("=")[1], 0)
        end = int(argv[3].split("=")[1], 0)
        offset = start - FLASH_BASE
        length = end - start
    else:
        offset = int(argv[2], 0)
        length = int(argv[3], 0)

    for insn in disasm(data, offset, length):
        print(f"0x{insn.address:08x}: {insn.mnemonic}\t{insn.op_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
