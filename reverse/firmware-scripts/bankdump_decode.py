#!/usr/bin/env python3
"""Decode a Tanzmaus *bank dump* SysEx capture into per-pattern blobs.

Unlike the firmware-update .syx (see fw_decoder.py, cmd 0x01), the bank dump
(cmd 0x03) uses a different 7->8 pack and must be fed its own converter:

  Windfisch/tanzmaus-reversing  util.py::convert_7to8
   - for every frame take payload7 = frame[10:-1] and drop the last 4 bytes
     (a trailing per-frame checksum / derived value, see factory-patterns.md)
   - 7->8: concatenate the REVERSED low-7-bits of each byte, then cut 8-bit
     bytes from the front (reversed-bit per-byte order)
   - per pattern: 13 frames of 317 B (parts 0..0x0C) yielding 264 B each
     + 1 frame of 84 B (part 0x0D) yielding 60 B = 3492 B raw
   - strip the first 16 bits (pattern id + 00) -> 3490 B = 0x0DA2 per pattern,

  verified against the 1-16 factory bank (mfb/..factory patterns.syx) and the
  front-panel dump baseline (reverse/sysex-probes/bank-dump-baseline.syx).

The bit order here differs from the firmware varint in fw_decoder.py (that one
is LSB-first with no per-byte reversal); do NOT feed bank-dump payloads to the
firmware unpacker.
"""
from __future__ import annotations

import sys
from pathlib import Path

MFB_ID = b"\x00\x21\x0b"
HDR = b"\x04\x00\x03\x00\x00"
LONG_FRAME = 317
SHORT_FRAME = 84
PAYLOAD_PER_PART = {  # decoded 8-bit bytes contributed per part
    0x00: 264,
    0x0D: 60,
}


def split_sysexes(data: bytes) -> list[bytes]:
    parts = data.split(b"\xf0")
    if not parts[0]:
        parts = parts[1:]
    return [b"\xf0" + t for t in parts if t]


def convert_7to8(payload: bytes) -> bytes:
    """Windfisch convert_7to8: reversed low-7-bits stream -> 8-bit bytes."""
    bits = []
    for b in payload:
        bits.append(f"{b & 0x7f:07b}"[::-1])
    stream = "".join(bits)
    out = bytearray()
    for i in range(0, len(stream) - 7, 8):
        out.append(int(stream[i:i + 8], 2))
    if "1" in stream[len(out) * 8:]:
        raise ValueError("convert_7to8: nonzero remainder")
    return bytes(out)


def parse_bank_dump(sysexes: list[bytes]) -> list[bytes]:
    """Validate framing and return 16 per-pattern blobs (3490 B each).

    Raises ValueError on any structural/invariant violation; otherwise the
    framing is comprehensive (header, part/pattern sequencing, lengths, and
    the decoder's zero-remainder check all pass).
    """
    patterns: list[bytes] = []
    expected_part = 0
    for bs in sysexes:
        if bs[0] != 0xF0:
            raise ValueError(f"frame lacks F0: {bytes(bs[:4]).hex()}")
        if bs[-1] != 0xF7:
            raise ValueError(f"frame lacks F7: {bytes(bs[-4:]).hex()}")
        if bs[1:4] != MFB_ID:
            raise ValueError(f"bad MFB id: {bs[1:4].hex()}")
        if bs[4:9] != HDR:
            raise ValueError(f"bad transfer/command header: {bs[4:9].hex()}")

        part = bs[9]
        if part != expected_part:
            raise ValueError(f"unexpected part {part}, expected {expected_part}")
        expected_part = expected_part + 1 if expected_part < 0x0D else 0

        if part == 0:
            if bs[11] != 0x00:
                raise ValueError(f"byte after pattern no not 00: {bs[11]:02x}")
            patterns.append(b"")

        expected_len = LONG_FRAME if part != 0x0D else SHORT_FRAME
        if len(bs) != expected_len:
            raise ValueError(f"frame len {len(bs)} != {expected_len} (part {part})")

        payload7 = bs[10:-1][:-4]
        patterns[-1] += convert_7to8(payload7)

    if len(patterns) != 16:
        raise ValueError(f"expected 16 patterns, got {len(patterns)}")
    out = []
    for i, p in enumerate(patterns):
        if p[1] != 0x00:
            raise ValueError(f"pattern {i} second byte not 00: {p[1]:02x}")
        out.append(p[2:])
    return out


def dump_frame_stats(sysexes: list[bytes]) -> dict:
    parts: dict[int, int] = {}
    for bs in sysexes:
        parts[bs[9]] = parts.get(bs[9], 0) + 1
    return {"frames": len(sysexes), "parts": parts}


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("syx", help="bank dump .syx capture")
    ap.add_argument("-o", "--outdir", default=".",
                    help="write extracted per-pattern blobs here as <nn>-p.bin")
    ap.add_argument("--verify-only", action="store_true",
                    help="validate framing only (no extraction)")
    args = ap.parse_args()

    sysexes = split_sysexes(open(args.syx, "rb").read())
    stats = dump_frame_stats(sysexes)
    print(f"frames: {stats['frames']}")
    print(f"part histogram: {dict(sorted(stats['parts'].items()))}")

    if args.verify_only:
        return 0

    patterns = parse_bank_dump(sysexes)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(patterns):
        if len(p) != 3490:
            raise ValueError(f"pattern {i} decoded to {len(p)} B (expected 3490)")
        (outdir / f"{i:02d}-p.bin").write_bytes(p)
        print(f"pattern {i:2d}: {len(p)} B -> {outdir}/{i:02d}-p.bin")
    return 0


if __name__ == "__main__":
    sys.exit(main())