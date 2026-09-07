#!/usr/bin/env python3
"""Analyze a decoded Tanzmaus firmware image for SysEx command handling.

Usage:
  fw_dispatcher.py <file.syx> [<out.bin>]
      Decode the firmware image, disassemble it, and report:

        - real vector-table candidates (4-aligned; the 0x1ef 'vectors' are
          not ARM-legal for an exception table),
        - peripheral base constants built by adjacent movw/movt pairs
          (RCC / GPIO / USART / timers),
        - register accesses at the USART-shaped offsets 0x1c/0x20/0x24/0x28
          (ISR/ICR/RDR/TDR on STM32F3),
        - SysEx parser candidate windows (code that references the F0/F7
          frame delimiters together with the MFB header bytes 0x21/0x0b),
        - candidate command-dispatch compares (`cmp rX,#imm`->branch) inside
          those windows.

  fw_dispatcher.py <file.syx> --window=<addr> --len=<n>
      Printable disassembly of the flash range [addr, addr+len).
      Reminder: the linear Thumb-2 decode runs through data tables, so not
      every printed line is an executed instruction; use ranges aligned to
      parser candidates flagged in the default report.

Heuristic scope: no full control-flow graph is built. The command set is
inferred from compare/site statistics and must be cross-checked against the
live probe results (reverse/sysex-probes.md).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

from fw_decoder import parse_frames, unpack7

FLASH_BASE = 0x08000000
FLASH_MAX = 0x08040000
SRAM_LOW = 0x20000000
SRAM_HIGH = 0x20010000

USART_OFFSETS = {0x1C: "ISR", 0x20: "ICR", 0x24: "RDR+", 0x28: "TDR+"}


def decode_image(path: Path) -> bytes:
    frames = parse_frames(path)
    if not frames:
        raise ValueError(f"{path}: no firmware frames")
    max_addr = max(a for a, _ in frames)
    return b"".join(unpack7(p) for a, p in sorted(frames) if a != max_addr)


def disasm_all(image: bytes):
    """Single-pass Thumb-2 decode that survives data runs (resume after stall)."""
    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    insns = []
    off = 0
    while off < len(image) - 3:
        sub = md.disasm(image[off:], FLASH_BASE + off)
        consumed = 0
        last = None
        for insn in sub:
            insns.append(insn)
            consumed += insn.size
            last = insn.address + insn.size
        if consumed:
            off += consumed
        else:
            off += 2
    insns.sort(key=lambda i: i.address)
    return insns


def adj_movw_movt(insns):
    """Map full 32-bit constants built by adjacent `movw`/`movt` to the movw addr."""
    out = {}
    for i in range(len(insns) - 1):
        a, b = insns[i], insns[i + 1]
        if a.mnemonic == "movw" and b.mnemonic == "movt" and "#" in a.op_str and "#" in b.op_str:
            ra = a.op_str.split(",")[0].strip()
            rb = b.op_str.split(",")[0].strip()
            if ra == rb:
                try:
                    lo = int(a.op_str.split("#")[1], 16)
                    hi = int(b.op_str.split("#")[1], 16)
                    out.setdefault((hi << 16) | lo, []).append(a.address)
                except ValueError:
                    pass
    return out


def vector_tables(image: bytes):
    """4-aligned positions where an SRAM word is followed by flash function ptrs."""
    found = []
    for pos in range(0, len(image) - 64, 4):
        w0 = struct.unpack_from("<I", image, pos)[0]
        if not (SRAM_LOW <= w0 <= SRAM_HIGH):
            continue
        words = struct.unpack_from("<10I", image, pos + 4)
        n = sum(1 for w in words if FLASH_BASE <= (w & ~1) < FLASH_MAX)
        if n >= 6:
            found.append((FLASH_BASE + pos, w0, n, words[:6]))
    return found


def usart_accesses(insns):
    sites = {"r": [], "w": []}
    for insn in insns:
        if insn.mnemonic in ("strb", "str", "strh") and "#0x" in insn.op_str:
            mnem = insn.mnemonic
            off = 0x28 if "#0x28" in insn.op_str else None
            if off is not None:
                sites["w"].append((insn.address, mnem))
        if insn.mnemonic in ("ldrb", "ldr", "ldrh") and "#0x24" in insn.op_str:
            sites["r"].append((insn.address, insn.mnemonic))
    return sites


def parser_windows(insns, span=320):
    """Windows around F0/F7 compares that also contain header-byte compares."""
    def imm_of(insn):
        if insn.mnemonic in ("cmp", "cmp.w") and "#0x" in insn.op_str:
            try:
                return int(insn.op_str.split("#")[1], 16)
            except ValueError:
                return None
        return None

    f0 = [i for i in insns if imm_of(i) == 0xF0]
    f7 = [i for i in insns if imm_of(i) == 0xF7]
    head_imms = {0x21, 0x0B, 0x04, 0x00}

    windows = []
    for center in f0 + f7:
        lo, hi = center.address - span, center.address + span
        win = {}
        has_head = False
        for insn in insns:
            if lo <= insn.address <= hi:
                v = imm_of(insn)
                if v is not None:
                    win[v] = win.get(v, 0) + 1
                if v in head_imms:
                    has_head = True
        windows.append((center.address, has_head, win))
    # merge overlapping, keep only windows with header-bytes present
    candidates = []
    for addr, has_head, win in windows:
        if not has_head:
            continue
        if candidates and addr - candidates[-1][-1][0] <= span:
            candidates[-1].append((addr, win))
        else:
            candidates.append([(addr, win)])
    merged = []
    for group in candidates:
        low_win = {}
        for _, win in group:
            for v, n in win.items():
                low_win[v] = low_win.get(v, 0) + n
        merged.append({
            "lo": group[0][0] - span,
            "hi": group[-1][0] + span,
            "cmp_imms": low_win,
            "hits": [a for a, _ in group],
        })
    return merged


def literal_pools(image, insns):
    """Distinct 32-bit words loaded via `ldr rX,[pc,#k]` (Thumb-1/2 literal pools)."""
    from collections import Counter
    pools = Counter()
    for insn in insns:
        if insn.mnemonic in ("ldr", "ldrb", "ldrh", "ldr.w") and "[pc" in insn.op_str:
            try:
                k = int(insn.op_str.split("#")[1].split("]")[0], 16)
            except (ValueError, IndexError):
                continue
            base = (insn.address + 4) & ~3
            off = base + k - FLASH_BASE
            if 0 <= off <= len(image) - 4:
                pools[struct.unpack_from("<I", image, off)[0]] += 1
    return pools


def command_inventory(insns):
    """Global histogram of `cmp rX,#imm` immediates 1..0x7f (command-byte candidates)."""
    from collections import Counter
    hist = Counter()
    first = {}
    for insn in insns:
        if insn.mnemonic not in ("cmp", "cmp.w") or "#0x" not in insn.op_str:
            continue
        try:
            v = int(insn.op_str.split("#")[1], 16)
        except ValueError:
            continue
        if 0 < v <= 0x7F:
            hist[v] += 1
            first.setdefault(v, insn.address)
    return hist, first


def window_disasm(image, insns, lo, hi, mark=(0x21, 0x0B, 0xF0, 0xF7), out=None):
    lines = []
    for insn in insns:
        if lo <= insn.address <= hi:
            if out is not None and insn.address >= out and insn.address < hi:
                continue
            tag = ""
            try:
                v = int(insn.op_str.split("#")[1], 16) if "#0x" in insn.op_str else None
            except ValueError:
                v = None
            if v in mark:
                tag = "  <<<"
            lines.append(f"{insn.address:08x}: {insn.mnemonic:8s} {insn.op_str}{tag}")
    return lines


def main(argv):
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    path = Path(argv[1])
    image = decode_image(path)
    print(f"{path.name}: image {len(image)} bytes  base {FLASH_BASE:08x}")

    if len(argv) > 2 and argv[2].startswith("--window="):
        lo = int(argv[2].split("=")[1], 0)
        hi = lo + int(argv[3].split("=")[1], 0) if len(argv) > 3 else lo + 0x80
        insns = disasm_all(image)
        print(f"--- disasm {lo:08x}..{hi:08x} ---")
        for line in window_disasm(image, insns, lo, hi):
            print("  " + line)
        return 0

    if len(argv) >= 3 and not argv[2].startswith("--"):
        Path(argv[2]).write_bytes(image)
        print(f"  wrote image: {argv[2]}")

    insns = disasm_all(image)
    print(f"decoded instructions: {len(insns)}")

    pools = literal_pools(image, insns)
    print("\n== literal-pool words of interest (ldr rX,[pc,#k]) ==")
    interesting = sorted((w, n) for w, n in pools.items()
                         if 0x40000000 <= w < 0x50000000 or 0xE0000000 <= w < 0xF0000000)
    if interesting:
        for w, n in interesting:
            print(f"  {w:08x} x{n}")
    else:
        print("  none in 0x4x/0xExF space")

    hist, first = command_inventory(insns)
    print("\n== global cmp #imm 1..0x7f inventory (top; candidate command bytes) ==")
    for v, n in sorted(hist.items(), key=lambda kv: -kv[1])[:40]:
        print(f"  cmp #{v:#04x} ({v:3d}) x{n}   first@{hex(first[v])}")

    print("\n== vector-table candidates (4-aligned, SRAM w0 + >=6 flash words) ==")
    vts = vector_tables(image)
    if vts:
        for pos, w0, n, words in vts:
            print(f"  flash {pos:08x}: sp={w0:08x} fp={n} {''.join('%08x ' % w for w in words[:4])}")
    else:
        print("  none found — exception vectors are not in a standard layout.")

    print("\n== adjacent movw/movt peripheral constants ==")
    pairs = adj_movw_movt(insns)
    periphs = {0x40004400: "USART2", 0x40004800: "USART3", 0x40004C00: "UART4",
               0x40005000: "UART5", 0x40013800: "USART1", 0x40014400: "TIM16",
               0x40021000: "RCC", 0x48000000: "GPIOA", 0x48000400: "GPIOB",
               0x48000800: "GPIOC", 0x48000C00: "GPIOD", 0x40020000: "DMA1",
               0x40013000: "SPI1", 0x40005400: "I2C1", 0xE000ED00: "SCB"}
    for base in sorted(pairs):
        tag = periphs.get(base)
        if tag or base >> 16 in (0x4000, 0x4001, 0x4002, 0x4800, 0x5000):
            addrs = pairs[base]
            print(f"  {base:08x} {tag or '':10s} sites={len(addrs)} first={hex(addrs[0])}"
                  + (f" ...{hex(addrs[-1])}" if len(addrs) > 1 else ""))

    print("\n== USART-shaped register accesses ==")
    sites = usart_accesses(insns)
    print(f"  TDR writes (#0x28 offset): {len(sites['w'])}   RDR reads (#0x24): {len(sites['r'])}")
    for a, m in sites["w"][:10]:
        print(f"    {hex(a)}: {m}")

    print("\n== SysEx parser candidate windows ==")
    windows = parser_windows(insns)
    if not windows:
        print("  none")
    for w in windows:
        cmds = sorted(v for v in w["cmp_imms"] if 0 < v <= 0x7F)
        # highlight likely command-dispatch imms
        cmd_str = " ".join(f"{v:#04x}" for v in cmds)
        print(f"  window {w['lo']:08x}-{w['hi']:08x}  hits={[hex(h) for h in w['hits']]}")
        print(f"    cmp-imms (<=0x7f): {cmd_str}")

    print("\n== command-dispatch clusters: cmp #imm -> branch, near SysEx ==")
    seen = set()
    for w in windows:
        lo, hi = w["lo"], w["hi"]
        for i, insn in enumerate(insns):
            a = insn.address
            if not (lo <= a <= hi):
                continue
            if insn.mnemonic not in ("cmp", "cmp.w") or "#0x" not in insn.op_str:
                continue
            try:
                v = int(insn.op_str.split("#")[1], 16)
            except ValueError:
                continue
            if 0 < v <= 0x7F and i + 1 < len(insns):
                nxt = insns[i + 1]
                if nxt.mnemonic in ("beq", "bne", "beq.w", "bne.w", "cbz", "cbnz"):
                    key = (lo, hex(v), hex(nxt.address))
                    if key not in seen:
                        seen.add(key)
                        print(f"    win {lo:08x}: cmp #{v:#04x} then {nxt.mnemonic} @{hex(nxt.address)}")

    print("\ndone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))