#!/usr/bin/env python3
"""Reconstruct the MFB Tanzmaus firmware image from an official .syx update file.

Decode recipe (see firmware.md):
  1. Split the .syx on F0 into SysEx frames.
  2. For each frame (cmd 0x01) take the 38 payload bytes (cols 10..47).
     The frame at addr max-1 is shorter than 52 bytes (the image is not
     33-byte aligned): it carries the image tail and has no checksum field.
  3. Per-frame LSB-first 7->8 unpack (acc |= (b&0x7f)<<nb; emit low byte when nb>=8).
  4. Concatenate frames in address order 1..max-1, EXCLUDING the metadata header
     frame at addr = max.
  5. The result is the flash image, base 0x08000000.

Empirical layout (verified across V1.6/V1.61/V1.62/V1.63):
  addr 1..max-2  -> full 52-byte data frames (38 payload + 3-byte checksum)
  addr max-1     -> final (short) data frame, 29..48 bytes, no checksum field
  addr max       -> metadata header frame (52 bytes), addr == total frame count

Self-checks:
  - addresses contiguous 1..max with no duplicates (structural)
  - the 3-byte checksum of every full 52-byte frame verifies (recovered table)
  - no standard Cortex-M vector table is claimed: the leading zero run is only
    0x62 bytes and image offset 0x1ef is not 4-aligned (see firmware.md,
    "Known issue"), so the old vector-table self-check was removed.
"""
from __future__ import annotations

import sys
from pathlib import Path

FLASH_BASE = 0x08000000
FLASH_MAX = 0x08040000  # 256 KB


def split_frames(data: bytes) -> list[bytes]:
    # util.split_sysexes: first byte is lost; re-prefix with F0
    parts = data.split(b"\xf0")
    if not parts[0]:
        parts = parts[1:]
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


def parse_frames(path: Path) -> list[tuple[int, bytes]]:
    """Return (addr, payload) for every cmd-01 frame in the file.

    `payload` is the 38-byte payload (cols 10..47) for full 52-byte frames and
    the raw tail bytes (cols 10..len-2, F7 excluded) for short frames.
    """
    data = path.read_bytes()
    frames = []
    for f in split_frames(data):
        if len(f) < 11 or f[0] != 0xF0 or f[-1] != 0xF7:
            raise ValueError(f"{path}: malformed frame ({len(f)} bytes)")
        if f[6] != 0x01:
            continue  # only firmware upload frames
        addr = (f[8] << 7) | f[9]
        if len(f) == 52:
            payload = f[10:48]
        else:
            payload = f[10:-1]  # short frame: no checksum field, drop F7
        frames.append((addr, payload))
    return frames


def frame_fields(path: Path):
    """Yield (addr, frame_len, payload, ck) for cmd-01 frames; ck None if short."""
    data = path.read_bytes()
    for f in split_frames(data):
        if len(f) < 11 or f[0] != 0xF0 or f[-1] != 0xF7:
            raise ValueError(f"{path}: malformed frame ({len(f)} bytes)")
        if f[6] != 0x01:
            continue
        addr = (f[8] << 7) | f[9]
        if len(f) == 52:
            yield addr, 52, f[10:48], f[48:51]
        else:
            yield addr, len(f), f[10:-1], None


def split_segments(frames: list[tuple[int, bytes]]):
    """Split parsed frames into (data, final, header).

    data   = addr 1..max-2, full 52-byte frames, in addr order
    final  = frame at addr max-1 (short frame = image tail)
    header = frame at addr max (metadata header)
    Raises ValueError on gaps, duplicates, or a non-contiguous address space.
    """
    if not frames:
        raise ValueError("no firmware frames")
    addrs = sorted(a for a, _ in frames)
    max_addr = addrs[-1]
    for i, a in enumerate(addrs, start=1):
        if a != i:
            raise ValueError(f"addresses not contiguous 1..{max_addr} (break at {a})")
    by_addr = dict(frames)
    if len(by_addr) != len(frames):
        raise ValueError("duplicate frame addresses")
    data = [(a, by_addr[a]) for a in range(1, max_addr - 1)]
    return data, by_addr[max_addr - 1], by_addr[max_addr]


def decode(path: Path) -> dict:
    """Decode a .syx firmware file; return a full report dict."""
    frames = parse_frames(path)
    data, final, header = split_segments(frames)
    image = b"".join(unpack7(p) for _, p in data) + unpack7(final)
    if not image:
        raise ValueError(f"{path}: empty image")

    leading_zero = 0
    for b in image:
        if b == 0:
            leading_zero += 1
        else:
            break

    total = len(frames)
    max_addr = len(frames)  # contiguous 1..max => max == total
    checked = ok = 0
    bad = []
    hlen = flen = None
    for addr, flen_, payload, ck in frame_fields(path):
        if addr == max_addr:
            hlen = flen_
        elif addr == max_addr - 1:
            flen = flen_
        if ck is None:
            continue
        checked += 1
        expected = _cksum_bytes(addr, payload)
        if expected != ck:
            bad.append(addr)
        else:
            ok += 1

    return {
        "path": path,
        "total_frames": total,
        "max_addr": max_addr,
        "header_addr": max_addr,
        "header_len": hlen,
        "final_addr": max_addr - 1,
        "final_len": flen,
        "data_frames": len(data),
        "image_size": len(image),
        "leading_zero": leading_zero,
        "checksums_checked": checked,
        "checksums_ok": ok,
        "checksum_mismatches": bad,
        "ok": (
            checked == len(data) + 1   # all data frames + the header frame
            and ok == checked
            and not bad
            and hlen == 52
        ),
    }


def _cksum_bytes(addr: int, payload38: bytes) -> bytes:
    import importlib
    ck = importlib.import_module("fw_cksum")
    return ck.frame_checksum_bytes(addr, payload38)


def main(argv):
    if len(argv) < 2:
        print("usage: fw_decoder.py <file.syx> [<out.bin>]", file=sys.stderr)
        return 2

    path = Path(argv[1])
    info = decode(path)
    print(f"{info['path'].name}:")
    print(f"  total frames    : {info['total_frames']}  (addr 1..{info['max_addr']}, contiguous, 1/addr)")
    print(f"  data frames     : {info['data_frames']}  (addr 1..{info['max_addr'] - 2}, 52 bytes)")
    print(f"  final frame     : addr {info['final_addr']}, {info['final_len']} bytes (image tail)")
    print(f"  metadata header : addr {info['header_addr']:04x}, {info['header_len']} bytes")
    print(f"  image size      : {info['image_size']} bytes ({info['image_size'] // 1024} KB)  base {FLASH_BASE:08x}")
    print(f"  leading zero run: 0x{info['leading_zero']:x}")
    print(f"  checksums (3-byte): {info['checksums_ok']}/{info['checksums_checked']} verified"
          + (f"  MISMATCH: {info['checksum_mismatches']}" if info["checksum_mismatches"] else ""))
    print(f"  decode OK       : {info['ok']}")

    if len(argv) >= 3:
        Path(argv[2]).write_bytes(b"".join(unpack7(p) for a, p in sorted(
            parse_frames(path), key=lambda x: x[0]) if a != info["max_addr"]))
        print(f"  wrote           : {argv[2]}")

    return 0 if info["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))