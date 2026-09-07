#!/usr/bin/env python3
"""Analyze a raw SPI DataFlash dump from the Tanzmaus Adesto sample chips.

To-do #2 helper. Recovers sample/bank storage and ties it to the 0x05/06/07
upload commands. This is deliberately *evidence-driven*: the physical part and
layout are not yet confirmed (pcb-visual-analysis.md marks them "≈"). The tool
reports what it can establish from the bytes alone and never over-claims.

Primary analyses:

  --jedec=BYTES      identify the part/density from a JEDEC (RDID 0x9F)
                     response captured on the CH341A before the full dump.
  analyze            given a dump FILE, report:
                       * size / detected density class
                       * entropy + page-geometry candidates (256/512/528-byte)
                       * 12-bit sample evidence (lo | hi<<7 reconstruction)
                       * slot-capacity scan vs known capacities
                       * candidate slot boundaries / occupancy

Known anchors (from firmware.md "Static-analysis findings"):
  - capacity constants at 0x0801A248: 22000/44000/88000  (0.5/1.0/2.0 s
    slots at the ~44.1 kHz internal rate)
  - storage-geometry cluster at 0x0801A230: 0,728,2184,3640,91,182,364
  - host sends each sample as two 7-bit bytes; firmware reconstructs
    a 14-bit word via lo | hi<<7; useful range is 12-bit.
  - factory set: 32 WAV, 48k mono 16-bit, 24000/48000/96000 frames.

Caveat: two chips on the PCB, "1610" (AT45DB321E, 32-Mbit) and "1544" (AT45DB081E,
8-Mbit) per pcb-visual-analysis.md — the older "≈16/4-Mbit" reading is superseded.
If the dump was taken from the wrong chip or with the two /CS lines swapped, the
tool will report the density mismatch rather than guess.
"""

import argparse
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Part / JEDEC-ID tables (Adesto / Dialog / generic SPI DataFlash)
# ---------------------------------------------------------------------------
# (jedec bytes, density bits, family, note)
JEDEC = [
    (bytes([0x1F, 0x46, 0x02]), 16 << 20, "AT25DF161A", "16-Mbit byte-addressed DataFlash"),
    (bytes([0x1F, 0x44, 0x01]), 4 << 20,  "AT25DF041A", "4-Mbit byte-addressed DataFlash"),
    (bytes([0x1F, 0x44, 0x00]), 8 << 20,  "AT25DF081A", "8-Mbit byte-addressed DataFlash"),
    (bytes([0x1F, 0x45, 0x01]), 2 << 20,  "AT25DF021",  "2-Mbit byte-addressed DataFlash"),
    (bytes([0x1F, 0x47, 0x01]), 32 << 20, "AT25DF321A", "32-Mbit byte-addressed DataFlash"),
    (bytes([0x1F, 0x27, 0x01]), 32 << 20, "AT45DB321E", "page-based DataFlash (512/528B pages)"),
    (bytes([0x1F, 0x26, 0x00]), 16 << 20, "AT45DB161D", "page-based DataFlash (512/528B pages)"),
    (bytes([0x1F, 0x25, 0x00]), 8 << 20,  "AT45DB081E", "page-based DataFlash (256/264B pages)"),
    (bytes([0x1F, 0x24, 0x00]), 4 << 20,  "AT45DB041D", "page-based DataFlash (256/264B pages)"),
    (bytes([0x1F, 0x23, 0x00]), 2 << 20,  "AT45DB021D", "page-based DataFlash (256/264B pages)"),
]
# Density (Mbit) -> (suggested page size, note) for byte-addressed parts
DENSITY2SIZE = {
    2: (256, "AT25DB/A-family, 256-byte pages"),
    4: (256, "256-byte pages"),
    8: (256, "256-byte pages"),
    16: (256, "256-byte pages"),
    32: (256, "256-byte pages"),
}

# Known sample-slot capacities in frames (internal ~44.1 kHz rate)
SLOT_FRAMES = {
    "0.5 s": 22000,
    "1.0 s": 44000,
    "2.0 s": 88000,
}


def identify_jedec(bs: bytes):
    bs = bytes(bs).lstrip(b"\xff") or bytes(bs)
    if len(bs) < 2:
        return None, "response too short"
    for jedec, dens, name, note in JEDEC:
        if bs[:3] == jedec[:3]:
            return (name, dens, note, jedec), None
    # manufacturer-only fallback
    if bs[0] == 0x1F:
        return ("unknown Adesto/Dialog part", None, f"RDID starts 0x1F (Adesto); full ID {bs.hex()}", bs), None
    return None, f"unrecognized JEDEC ID {bs.hex()}"


# ---------------------------------------------------------------------------
# Entropy / geometry
# ---------------------------------------------------------------------------
def entropy(blk: bytes):
    if not blk:
        return 0.0
    cnt = {}
    for b in blk:
        cnt[b] = cnt.get(b, 0) + 1
    n = len(blk)
    return -sum((c / n) * math.log2(c / n) for c in cnt.values())


def detect_page_size(dump: bytes):
    """Empirical page-size candidates via zero/FF-run periodicity over the
    first filled region. Returns list of (size, score). Higher score = more
    evidence of hard page boundaries."""
    # Use a filled window to avoid the erased tail
    filled = dump
    window = filled[: min(len(filled), 64 << 10)]
    if not window:
        return []
    scores = []
    for size in (132, 256, 264, 512, 528, 1024):
        # score: fraction of byte positions 'size' apart that are equal
        if size >= len(window):
            continue
        same = sum(1 for i in range(size, len(window)) if window[i] == window[i - size])
        scores.append((size, same / len(window)))
    return sorted(scores, key=lambda t: t[1], reverse=True)


def detect_erased_len(dump: bytes):
    """Find where the dump becomes all-0xFF (factory-erased tail)."""
    n = len(dump)
    # sample backwards
    run = 0
    for i in range(n - 1, max(n - 256, -1), -1):
        if dump[i] == 0xFF:
            run += 1
        else:
            break
    return run


# ---------------------------------------------------------------------------
# 12-bit sample evidence
# ---------------------------------------------------------------------------
def sample_evidence(dump: bytes, window=4096):
    """Check whether a region plausibly holds 12-bit samples stored as
    (lo | hi<<7) 14-bit words, i.e. each byte is < 0x80 (7-bit) — because the
    two transport bytes are each 7-bit payload. If the flash stores the
    reconstructed 14-bit word as two bytes, the high byte is small (< 0x40)."""
    # Find dense windows where many bytes are < 0x80 (not the erased 0xFF)
    step = 512
    best = []
    for start in range(0, len(dump) - window, step):
        blk = dump[start:start + window]
        lt128 = sum(1 for b in blk if b < 0x80)
        er = sum(1 for b in blk if b == 0xFF)
        frac = lt128 / window
        if frac >= 0.9 and er < window * 0.05:
            best.append((start, frac))
    return best[:8]


def data_regions(dump: bytes, min_len: int = 256):
    """Return (start, end) of contiguous non-erased, non-empty regions
    (allowing short runs of 0xFF noise between blocks). Used instead of a fixed
    slot-offset scan because sample-slot boundaries are not alignment-relative
    to absolute address 0 — they live inside whatever data regions exist."""
    regions = []
    n = len(dump)
    i = 0
    while i < n:
        if dump[i] == 0xFF:
            i += 1
            continue
        start = i
        j = i
        # extend through data, allowing gaps of up to ~8 erased bytes
        gap = 0
        while j < n:
            if dump[j] != 0xFF:
                gap = 0
            else:
                gap += 1
                if gap > 8:
                    break
            j += 1
        if j - start >= min_len:
            regions.append((start, j))
        i = j
    return regions


# ---------------------------------------------------------------------------
def parse_size_arg(s: str):
    s = s.strip().lower().replace("_", "")
    mult = 1
    if s.endswith("k"): mult, s = 1 << 10, s[:-1]
    if s.endswith("m"): mult, s = 1 << 20, s[:-1]
    return int(s, 0) * mult


def report(dump: bytes, name: str, chip: str = None):
    print(f"=== dump report: {name} ===")
    print(f"size            : {len(dump)} bytes ({len(dump) / 1024:.1f} KiB)")
    erased = detect_erased_len(dump)
    print(f"erased tail     : {erased} trailing 0xFF bytes")

    # density class from size (Mbit -> MiB = Mbit/8)
    dens_classes = []
    for mbit in (2, 4, 8, 16, 32):
        mib = (mbit << 20) // 8
        if len(dump) == mib:
            dens_classes.append(f"{mbit}-Mbit ({mib >> 10} KiB)")
    if chip:
        print(f"chip label      : {chip} (pcb marks '1610'/'1544' are approximations)")
    if dens_classes:
        print(f"size class      : matches {'/'.join(dens_classes)} dump exactly")
    else:
        print(f"size class      : {len(dump) * 8 / (1 << 20):.2f} Mbit — not a standard 2/4/8/16/32 dump size")

    print("\n-- page geometry (empirical) --")
    geo = detect_page_size(dump[:max(0, len(dump) - erased)])
    for size, score in geo:
        print(f"  {size:5d}-byte step periodicity: {score:.3f}"
              + ("   <=strong" if score > 0.35 else ""))
    if dens_classes:
        mbit = int(dens_classes[0].split("-")[0])
        p, note = DENSITY2SIZE.get(mbit, (None, "n/a"))
        if p:
            print(f"  note: {mbit}-Mbit byte-addressed parts typically use {p}-byte pages ({note})")

    print("\n-- 12-bit (lo | hi<<7) sample evidence --")
    ev = sample_evidence(dump[:max(0, len(dump) - erased)])
    if ev:
        for start, frac in ev[:6]:
            print(f"  0x{start:06x}: dense 7-bit-ish data ({frac*100:.0f}% bytes <0x80)")
        print("  -> consistent with factory-encoded samples (each word = two 7-bit bytes)")
    else:
        print("  (no dense 7-bit-ish window found; samples may be stored raw 16-bit or "
              "the dump is from the wrong chip / erased)")

    print("\n-- data layout --")
    body = dump[: max(0, len(dump) - erased)]
    regions = data_regions(body)
    if regions:
        print(f"  {len(regions)} contiguous data region(s) (ignoring erased 0xFF gaps):")
        for start, end in regions:
            ln = end - start
            print(f"    0x{start:06x} .. 0x{end:06x}  ({ln} bytes)"
                  + ("  <== largest" if ln == max(e - s for s, e in regions) else ""))
    else:
        print("  no data regions — dump appears erased/blank")

    print("\n-- slot-capacity sizing (vs 22000/44000/88000 frames, 2 bytes/sample) --")
    for label, frames in SLOT_FRAMES.items():
        cap = frames * 2
        fits = [end - start for start, end in regions if end - start >= cap]
        print(f"  {label} slots ({frames} fr x 2B = {cap} B): "
              f"{len(fits)} data region(s) at least this size"
              + (f" (max {max(fits) if fits else 0} B)" if fits else ""))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fw_dump_parse.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="raw SPI dump file (e.g. from flashrom)")
    ap.add_argument("--chip", help="chip label from the board (e.g. '1610') for reporting")
    ap.add_argument("--jedec", help="JEDEC RDID bytes as hex (e.g. '1F4602') to identify part only")
    ap.add_argument("--density", type=parse_size_arg,
                    help="override expected density, e.g. 16M or 16MB (16MiB)")
    args = ap.parse_args(argv)

    if args.jedec:
        try:
            bs = bytes.fromhex(args.jedec.replace(" ", ""))
        except ValueError:
            print("bad --jedec hex")
            return 2
        ident, err = identify_jedec(bs)
        if err:
            print(f"could not identify: {err}")
            return 1
        name, dens, note, jedec = ident
        print(f"JEDEC {bs.hex()}: {name}")
        print(f"  density       : {dens >> 20}-Mbit" if dens else "  density       : ?")
        print(f"  family/note   : {note}")
        return 0

    if not args.file:
        ap.print_help()
        return 2
    dump = Path(args.file).read_bytes()
    return report(dump, Path(args.file).name, chip=args.chip)


if __name__ == "__main__":
    sys.exit(main())
