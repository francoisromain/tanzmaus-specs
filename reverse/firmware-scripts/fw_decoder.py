#!/usr/bin/env python3
"""Reconstruct the MFB Tanzmaus firmware image from an official .syx update file.

Decode recipe (see firmware.md):
  1. Split the .syx on F0 into SysEx frames.
  2. For each 52-byte data frame (cmd 0x01) take the 38 payload bytes (cols 10..47).
  3. Per-frame LSB-first 7->8 unpack (acc |= (b&0x7f)<<nb; emit low byte when nb>=8).
  4. Concatenate frames in address order 1..N, EXCLUDING the metadata header frame
     (addr = max) and the trailer frame.
  5. The result is the flash image, base 0x08000000.

Self-checks:
  - The compact vector table must appear at image offset 0x1ef with the SRAM-top
    sentinel 0x2000a000 (40 KB SRAM) and a per-version reset vector in flash.
"""
from __future__ import annotations

import sys
from pathlib import Path

FLASH_BASE = 0x08000000
FLASH_MAX = 0x08040000  # 256 KB
SRAM_LOW = 0x20000000
SRAM_HIGH = 0x20010000
VT_OFFSET = 0x1EF


def split_frames(data: bytes) -> list[bytes]:
    # util.split_sysexes: first byte is lost; re-prefix with F0
    parts = data.split(b"\xf0")
    if not parts[0]:
        parts = parts[1:]
    else:
        # leading garbage before first F0; skip it
        pass
    return [b"\xf0" + t for t in parts if t]


def unpack7(payload: bytes) -> bytes:
    """Per-frame LSB-first 7->8 unpack."""
    out = bytearray()
    acc = 0
    nb = 0
    for x in payload:
        acc |= (x & 0x7F) << nb
        nb += 7
        while nb >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nb -= 8
    return bytes(out)


def parse_frames(path: Path):
    data = path.read_bytes()
    frames = []
    for f in split_frames(data):
        if len(f) < 11 or f[0] != 0xF0 or f[-1] != 0xF7:
            raise ValueError(f"{path}: malformed frame")
        if f[6] != 0x01:
            continue  # only firmware upload frames
        addr = (f[8] << 7) | f[9]
        # payload = data columns 10..47 (38 bytes); trailing checksum+F7 excluded
        payload = f[10:48]
        frames.append((addr, payload))
    return frames


def decode(path: Path):
    frames = parse_frames(path)
    if not frames:
        raise ValueError(f"{path}: no firmware frames")
    max_addr = max(a for a, _ in frames)
    data = sorted((a, p) for a, p in frames if a != max_addr)
    image = b"".join(unpack7(p) for _, p in data)

    leading_zero = 0
    for b in image:
        if b == 0:
            leading_zero += 1
        else:
            break

    sp = int.from_bytes(image[VT_OFFSET:VT_OFFSET + 4], "little")
    reset = int.from_bytes(image[VT_OFFSET + 4:VT_OFFSET + 8], "little")
    handlers = [
        int.from_bytes(image[VT_OFFSET + 4 * k:VT_OFFSET + 4 * k + 4], "little")
        for k in range(2, 7)
    ]

    ok = (SRAM_LOW <= sp < SRAM_HIGH
          and all(FLASH_BASE <= h < FLASH_MAX for h in [reset] + handlers))

    return {
        "path": path,
        "data_frames": len(data),
        "image_size": len(image),
        "leading_zero": leading_zero,
        "vt_offset": VT_OFFSET,
        "sp": sp,
        "reset": reset,
        "handlers": handlers,
        "ok": ok,
    }


def main(argv):
    if len(argv) < 2:
        print("usage: fw_decoder.py <file.syx> [<out.bin>]", file=sys.stderr)
        return 2

    path = Path(argv[1])
    info = decode(path)
    flash = "%08x" % (FLASH_BASE + info["vt_offset"])
    print(f"{info['path'].name}:")
    print(f"  data frames      : {info['data_frames']}")
    print(f"  image size       : {info['image_size']} bytes ({info['image_size']//1024} KB)")
    print(f"  leading zero run : 0x{info['leading_zero']:x}")
    print(f"  vector table     : image offset 0x{info['vt_offset']:x}  (flash {flash})")
    print(f"  initial SP       : 0x{info['sp']:08x}")
    print(f"  reset vector     : 0x{info['reset']:08x}  -> handler at 0x{FLASH_BASE + (info['reset']-FLASH_BASE):08x}")
    print(f"  fault handlers   : " + ", ".join("0x%08x" % h for h in info["handlers"]))
    print(f"  decode OK        : {info['ok']}")

    if len(argv) >= 3:
        frames = parse_frames(path)
        max_addr = max(a for a, _ in frames)
        image = b"".join(unpack7(p) for a, p in sorted(frames) if a != max_addr)
        Path(argv[2]).write_bytes(image)
        print(f"  wrote            : {argv[2]}")

    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
