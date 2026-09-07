#!/usr/bin/env python3
"""Find the app code that references specific SRAM / peripheral addresses.

The final frame of every firmware image embeds the RAM words 0x20000161 (or
0x20000165) and 0x200000bc. This script locates, in the reconstructed app
image, every instruction that constructs or loads those addresses, plus a
peripheral-constant inventory classified against the STM32F303 datasheet
memory map (reverse/STM32F303CCT6-datasheet.md).

Usage:
  fw_ramxref.py <file.syx> [<file2.syx> ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

import fw_dispatcher as fwd
from fw_decoder import parse_frames, unpack7

SRAM_LO, SRAM_HI = 0x20000000, 0x2000A000
WATCH_ADDRS = (0x20000161, 0x20000165, 0x200000bc)

PERIPHS = {
    0x40004400: "USART2", 0x40004800: "USART3", 0x40004C00: "UART4",
    0x40005000: "UART5", 0x40013800: "USART1", 0x40014000: "TIM15",
    0x40014400: "TIM16", 0x40014800: "TIM17", 0x40010000: "SYSCFG",
    0x40010400: "EXTI", 0x40007000: "PWR", 0x40021000: "RCC",
    0x40022000: "FLASH", 0x40023000: "CRC", 0x40020000: "DMA1",
    0x40020400: "DMA2", 0x48000000: "GPIOA", 0x48000400: "GPIOB",
    0x48000800: "GPIOC", 0x48000C00: "GPIOD", 0x48001000: "GPIOE",
    0x48001400: "GPIOF", 0x50000000: "ADC1-2", 0x50000400: "ADC3-4",
}

# candidate words for the raw byte-occurrence scan (immune to disassembly noise)
RAW_SCAN = WATCH_ADDRS + (0x20000164, 0x200000c4, 0x200000cc,
                          0x20000000, 0x2000a000, 0x40004400, 0x40013800)


def image_bytes(path: Path) -> bytes:
    frames = parse_frames(path)
    max_addr = len(frames)
    return b"".join(unpack7(p) for a, p in sorted(frames) if a != max_addr)


def windows(insns, addr, span=5):
    """Slice of instructions with a.within addr±span, else a small window push."""
    idx = {i.address: i for i in insns}
    done = set()
    for i in insns:
        lo, hi = i.address - span, i.address + span
        cur = sorted(a for a in idx if lo <= a <= hi)
        if not cur:
            continue
        key = (cur[0], cur[-1])
        if key in done:
            continue
        done.add(key)
        yield cur


def fmt_insn(i):
    return f"{i.address:08x}: {i.mnemonic:8s} {i.op_str}"


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    for arg in argv[1:]:
        path = Path(arg)
        img = image_bytes(path)
        insns = fwd.disasm_all(img)
        by_addr = {i.address: i for i in insns}

        pairs = fwd.adj_movw_movt(insns)
        pools = fwd.literal_pools(img, insns)

        print(f"=== {path.name} ===  image {len(img)} bytes")

        print("\n-- raw byte-occurrence counts (anywhere in the image; code or data) --")
        for w in RAW_SCAN:
            n = img.count(w.to_bytes(4, "little"))
            if n:
                print(f"  {w:08x}: {n}")

        pairs = fwd.adj_movw_movt(insns)
        pools = fwd.literal_pools(img, insns)

        print("\n-- movw/movt constants in SRAM (0x2000_xxxx) --")
        sram_sites = {}
        for w, sites in pairs.items():
            if SRAM_LO <= w <= SRAM_HI:
                sram_sites[w] = sorted(sites)
        for w in sorted(sram_sites):
            print(f"  {w:08x}: {len(sram_sites[w])} sites, first {hex(sram_sites[w][0])}"
                  + (f" ...{hex(sram_sites[w][-1])}" if len(sram_sites[w]) > 1 else ""))

        print("\n-- literal-pool words in SRAM (ldr [pc,#k]) --")
        sram_pools = {(w, n): [] for w, n in pools.items() if SRAM_LO <= w <= SRAM_HI}
        for w, n in sorted(sram_pools):
            print(f"  {w:08x} x{n}")

        print("\n-- windows around the image-tail RAM words --")
        for watch in WATCH_ADDRS:
            hits = set()
            for w, sites in (sram_sites.items()):
                if abs(w - watch) < 0x10:
                    hits.update(sites)
            for w, n in pools.items():
                if abs(w - watch) < 0x10:
                    pass  # pool hits add noise; keep movw/movt only
            if not hits:
                print(f"\n  {watch:08x}: no movw/movt construction sites")
                continue
            print(f"\n  {watch:08x}: constructing sites ->")
            seen_windows = set()
            for site in sorted(hits):
                lo, hi = site - 8, site + 8
                wkey = (lo, hi)
                if wkey in seen_windows:
                    continue
                seen_windows.add(wkey)
                print(f"    -- window @ 0x{site:08x} --")
                for i in insns:
                    if lo <= i.address <= hi:
                        mark = "  <<<" if i.address == site else ""
                        print(f"      {fmt_insn(i)}{mark}")

        print("\n-- peripheral constants (movw/movt) classified vs datasheet --")
        for base in sorted(pairs):
            if not (0x40000000 <= base < 0x50000000) and not (0xE0000000 <= base < 0xE0100000):
                continue
            tag = PERIPHS.get(base, "")
            sites = pairs[base]
            print(f"  {base:08x} {tag:10s} sites={len(sites)} first={hex(sites[0])}"
                  + (f" ...{hex(sites[-1])}" if len(sites) > 1 else ""))

        print("\n-- peripheral literal-pool words (top) --")
        interesting = sorted(((w, n) for w, n in pools.items()
                              if 0x40000000 <= w < 0x50000000 or 0xE0000000 <= w < 0xE0100000),
                             key=lambda kv: -kv[1])[:25]
        for w, n in interesting:
            tag = PERIPHS.get(w, "")
            print(f"  {w:08x} {tag:10s} x{n}")

        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))