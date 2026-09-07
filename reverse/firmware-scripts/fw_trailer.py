#!/usr/bin/env python3
"""Analyze the final (short) frame of an MFB Tanzmaus firmware update .syx.

The frame at addr max-1 is shorter than 52 bytes: the reconstructed image is
not 33-byte aligned, and this frame carries the image tail (with no 3-byte
checksum field). Unpacked per the same LSB-first 7->8 rule it yields the final
bytes of the flash image — genuine Thumb code with embedded RAM/flash pointers.

For every file this script reports:
  - the raw trailer frame (length + payload hex)
  - the unpacked bytes, disassembled as Thumb-2
  - embedded 32-bit words that reference SRAM (0x2000...) or flash (0x0800...)
  - image-level checksums of the earlier image (without the tail) for a quick
    global-signature comparison

Usage:
  fw_trailer.py <file.syx> [<file2.syx> ...]
"""
from __future__ import annotations

import binascii
import sys
import zlib
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

import fw_decoder
from fw_decoder import frame_fields, parse_frames, split_segments, unpack7

SRAM_LO, SRAM_HI = 0x20000000, 0x2000A000
FLASH_LO, FLASH_HI = 0x08000000, 0x08040000


def image(path: Path) -> bytes:
    """Reconstruct the image: data frames + final frame, header excluded."""
    frames = parse_frames(path)
    max_addr = len(frames)
    return b"".join(unpack7(p) for a, p in sorted(frames) if a != max_addr)


def trailer_parts(path: Path) -> tuple[int, bytes, bytes]:
    """Return (frame_len, payload, unpacked_bytes) of the final short frame."""
    frames = parse_frames(path)
    final_addr = len(frames) - 1
    flen = payload = None
    for addr, flen_, payload_, _ in frame_fields(path):
        if addr == final_addr:
            flen, payload = flen_, payload_
            break
    return flen, payload, unpack7(payload)


def image_checksums(img: bytes, tail_len: int) -> dict[str, int]:
    body = img[:-tail_len] if tail_len else img
    cks = {"crc32": zlib.crc32(body), "crc16": binascii.crc_hqx(body, 0)}
    cks["xor8"] = 0
    cks["sum8"] = 0
    for b in body:
        cks["xor8"] ^= b
        cks["sum8"] = (cks["sum8"] + b) & 0xFF
    return cks


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    for arg in argv[1:]:
        path = Path(arg)
        flen, payload, tail = trailer_parts(path)
        img = image(path)
        print(f"=== {path.name} ===")
        print(f"  frame len      : {flen} bytes   payload {len(payload)} bytes")
        print(f"  unpacked       : {len(tail)} bytes: {tail.hex()}")

        print("\n  embedded 32-bit words pointing into SRAM/flash:")
        shown = 0
        for off in range(0, len(tail) - 3):
            w = int.from_bytes(tail[off:off + 4], "little")
            if (SRAM_LO <= w < SRAM_HI) or (FLASH_LO <= w < FLASH_HI):
                region = "SRAM" if SRAM_LO <= w < SRAM_HI else "FLASH"
                print(f"    +0x{off:02x}: {w:08x} ({region})")
                shown += 1
        if not shown:
            print("    none")

        print("\n  all 32-bit words (LE) every 4 bytes:")
        for off in range(0, len(tail) - 3, 4):
            print(f"    +0x{off:02x}: {int.from_bytes(tail[off:off + 4], 'little'):08x}")

        body_len = len(img) - len(tail)
        print(f"\n  Thumb-2 disassembly of the tail, base 0x{FLASH_LO + body_len:08x}:")
        for insn in Cs(CS_ARCH_ARM, CS_MODE_THUMB).disasm(tail, FLASH_LO + body_len):
            print(f"    {insn.address:08x}: {insn.mnemonic:8s} {insn.op_str}")

        print("\n  image checksums (image minus final tail) / tail words:")
        cks = image_checksums(img, len(tail))
        print("    " + "  ".join(f"{k}={v:08x}" for k, v in cks.items()))
        print("    tail words:  " + " ".join(
            f"{(FLASH_LO + body_len) + off:08x}"
            f"={int.from_bytes(tail[off:off + 4], 'little'):08x}"
            for off in range(0, len(tail) - 3, 4)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))