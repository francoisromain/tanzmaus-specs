#!/usr/bin/env python3
"""Recursive-descent Thumb-2 control-flow analysis of the Tanzmaus firmware.

Builds a real control-flow graph (CFG) for the decoded application image,
replacing the linear-sweep approach used by fw_dispatcher.py. The firmware
has no standard vector table and no single clean entry point (see firmware.md),
so the tool:

  1. Collects candidate function roots:
       - constant `bl`/`blx #imm` targets found by an initial linear decode,
       - `push {..,lr}` prologue sites (real Thumb function prologues),
       - explicit `--seed=` addresses (e.g. boot-handoff manifest words).
  2. Recursively descends each candidate root, following only real branch
     edges (fall-through, conditional/unconditional b, cbz/cbnz, IT blocks)
     and stopping at returns (`bx lr`, `pop {..,pc}`) or undecodable data.
     Calls (`bl`/`blx #imm`) are recorded as edges but NOT inlined into the
     caller — each function body is walked independently, which keeps the
     per-function reach compact and matches the standard recursive-descent
     function-discovery model.
  3. Keeps a root as a *confirmed function* only if its walk is coherent:
     it reaches a return, stays within flash, and is reasonably dense
     (a tight region). Roots whose expansion wanders sparsely across a wide
     range are flagged as suspected data (from the linear-decode census).
  4. Inverts `bl` edges into the call graph and reports code-vs-data coverage.

The firmware image has no trustworthy single root, so the tool never claims
the reachable set is authoritative: every root starts as a *candidate* and is
classified confirmed / suspected-data / rejected, so a human can review the
boundary decisions the linear decode cannot make.

Usage:
  fw_cfg.py <file.syx> [--json=<out.json>] [--limit=<N>] [--seed=<A> ...] [--walk=<addr>]
      <file.syx>   an official MFB firmware .syx update file
      --json=      write the function map + call graph as JSON
      --limit=     cap candidate roots processed (default: all)
      --seed=      extra root address(es), flash space (repeatable), e.g. --seed=0x08012fc5
      --walk=<A>   recursively walk a single address and print its branch edges
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_OPT_DETAIL
from capstone.arm import ARM_OP_IMM

from fw_decoder import parse_frames, unpack7

FLASH_BASE = 0x08000000
FLASH_MAX = 0x08040000          # 256 KB
MAX_STEPS = 1 << 22             # hard bound on total instructions (anti-runaway)
MAX_FUNC_STEPS = 1 << 14        # bound per-function expansion

# Capstone group ids (verified in this environment)
GRP_JUMP = 1
GRP_CALL = 2
GRP_BRREL = 7

_PC = "pc"
_RET_OP_MNEM = ("bx", "blx")
_POP_PC = ("pop", "pop.w")


class Instr:
    """Minimal wrapper around a Capstone instruction plus our classification."""

    def __init__(self, insn):
        self.addr = insn.address
        self.size = insn.size
        self.mnemonic = insn.mnemonic
        self.op_str = insn.op_str

    def is_return(self) -> bool:
        m = self.mnemonic
        if m in _RET_OP_MNEM:
            return self.op_str.strip().lower() == "lr"
        if m in _POP_PC:
            return _PC in [o.strip().lower() for o in self.op_str.split(",")]
        return False

    @property
    def op0_type(self):
        return getattr(self, "_op0_type", None)

    @property
    def op0_imm(self):
        return getattr(self, "_op0_imm", None)


class CfgBuilder:
    def __init__(self, image: bytes, base: int = FLASH_BASE):
        self.image = image
        self.base = base
        self.md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
        self.md.detail = True
        self.steps = 0
        self.visited = set()
        self.functions = {}       # root -> dict
        self.root_status = {}     # root -> (ok, reason)

    # ---- decoding helpers ------------------------------------------------
    def _decode(self, addr: int):
        off = addr - self.base
        if off < 0 or off + 2 > len(self.image):
            return None
        for insn in self.md.disasm(self.image[off:], addr):
            w = Instr(insn)
            w._groups = frozenset(insn.groups)
            if insn.operands:
                o0 = insn.operands[0]
                w._op0_type = o0.type
                w._op0_imm = getattr(o0, "imm", None)
            return w
        return None

    def _imm_target(self, insn: Instr):
        if insn.op0_type == ARM_OP_IMM and insn.op0_imm:
            return insn.op0_imm & 0xFFFFFFFE
        return None

    def _in_flash(self, addr: int) -> bool:
        return FLASH_BASE <= addr < FLASH_MAX

    # ---- control-flow classification ------------------------------------
    def _classify(self, insn: Instr):
        """Return (kind, target, fallthrough)."""
        m = insn.mnemonic.rstrip(".w")
        groups = getattr(insn, "_groups", frozenset())
        tgt = None
        if m in ("bl", "blx", "cbz", "cbnz", "b", "bx") or GRP_JUMP in groups or GRP_BRREL in groups:
            tgt = self._imm_target(insn) if m != "bx" else None
            tgt = tgt if (tgt is None or self._in_flash(tgt)) else None

        if insn.is_return():
            return "ret", None, False
        if m == "bx":
            return "ind", None, False
        if m in ("cbz", "cbnz"):
            return "cond_br", tgt, True
        if m == "bl":
            return "call", tgt, True
        if m == "blx":
            if tgt is None:
                return "call_ind", None, True
            return "call", tgt, True
        if m == "b":
            return "br", tgt, False
        if GRP_BRREL in groups:            # b<cond>
            return "cond_br", tgt, True
        return "fall", None, True

    def _walk(self, root: int):
        """Walk one function body using recursive descent (calls not inlined)."""
        stack = [root]
        reached = set()
        bl_edges = set()       # (caller_addr, callee_addr)
        br_edges = set()       # (from, to) for non-call branches
        total = 0
        while stack and total < MAX_FUNC_STEPS and self.steps < MAX_STEPS:
            addr = stack.pop()
            if addr in reached:
                continue
            insn = self._decode(addr)
            if insn is None:
                continue
            reached.add(addr)
            self.visited.add(addr)
            total += 1
            self.steps += 1

            kind, tgt, fall = self._classify(insn)

            if kind == "ret":
                continue
            if kind == "call":
                if tgt is not None:
                    bl_edges.add((addr, tgt))
                if fall:
                    stack.append(addr + insn.size)
                continue
            if kind == "call_ind":
                if fall:
                    stack.append(addr + insn.size)
                continue
            if kind == "ind":
                continue
            if kind == "br":
                if tgt is not None:
                    br_edges.add((addr, tgt))
                    stack.append(tgt)
                continue
            if kind == "cond_br":
                if tgt is not None:
                    br_edges.add((addr, tgt))
                    stack.append(tgt)
                if fall:
                    stack.append(addr + insn.size)
                continue
            # fall
            stack.append(addr + insn.size)

        complete = total < MAX_FUNC_STEPS and not stack
        return reached, bl_edges, br_edges, complete

    # ---- root collection -------------------------------------------------
    def collect_roots(self, seeds=()):
        roots = set()
        for off in range(0, len(self.image) - 3, 2):
            insn = self._decode(self.base + off)
            if insn is None:
                continue
            m = insn.mnemonic
            if m in ("bl", "blx") and insn.op0_type == ARM_OP_IMM:
                t = self._imm_target(insn)
                if t is not None and self._in_flash(t):
                    roots.add(t)
            if m == "push" and "lr" in insn.op_str:
                roots.add(insn.addr)
        for s in seeds:
            roots.add(s)
        return sorted(roots)

    # ---- coherence / validation -----------------------------------------
    def _has_prologue(self, root: int) -> bool:
        """Real compiled Thumb functions almost always begin with
        `push {..., lr}` (or a `push {r4-r11}` / `mov r12, sp` variant).
        Requiring this at the root prunes the many data-derived `bl` targets
        that the linear decode produces."""
        insn = self._decode(root)
        if insn is None:
            return False
        if insn.mnemonic == "push" and "lr" in insn.op_str:
            return True
        # rare prologues: mov r12, sp / subs sp, #imm
        if insn.mnemonic in ("mov", "mov.w") and "r12" in insn.op_str and "sp" in insn.op_str:
            return True
        if insn.mnemonic in ("subs", "sub", "sub.w") and "sp" in insn.op_str:
            return True
        return False

    def _is_coherent(self, reached, root):
        """A walk is a plausible function if its root has a prologue, it hits
        at least one return, and its node set is locally dense. Sparse
        treks across a wide byte range indicate the walk ran through data."""
        if not reached:
            return False
        if not self._has_prologue(root):
            return False
        n_ret = 0
        for a in reached:
            i = self._decode(a)
            if i is not None and i.is_return():
                n_ret += 1
        if n_ret < 1:
            return False
        lo, hi = min(reached), max(reached)
        span = hi - lo + 1
        density = len(reached) / span if span else 0.0
        # Genuine Thumb bodies are tightly packed (~<8 bytes/node). A trek
        # whose density is below 1/12 is more consistent with data tables
        # joined by spurious branches.
        return density >= 1 / 12.0

    # ---- top-level analysis ---------------------------------------------
    def analyze(self, seeds=(), roots=None, limit=None):
        if roots is None:
            roots = self.collect_roots(seeds)
        if limit:
            roots = roots[:limit]

        for r in roots:
            reached, bl_edges, br_edges, complete = self._walk(r)
            if not reached:
                self.root_status[r] = (False, "no-decode")
                continue
            coherent = self._is_coherent(reached, r)
            if not coherent:
                self.root_status[r] = (False, f"no-prologue-or-sparse n={len(reached)}")
                continue
            self.functions[r] = {
                "root": r,
                "nodes": frozenset(reached),
                "bl_edges": bl_edges,
                "br_edges": br_edges,
            }
            self.root_status[r] = (True, f"n={len(reached)}")

        # merge alias roots: a root whose nodes are a subset of an existing
        # function is the same function (dedupe by node set)
        dedup = {}
        for r, f in self.functions.items():
            key = f["nodes"]
            if key not in dedup:
                dedup[key] = (r, f)
            else:
                # keep the lowest root as canonical
                prev_r, prev_f = dedup[key]
                if r < prev_r:
                    dedup[key] = (r, f)
        functions = {r: f for (r, f) in dedup.values()}
        self.functions = functions
        return self.build_report()

    def build_report(self):
        fn_list = []
        for r, f in self.functions.items():
            nodes = f["nodes"]
            callees = sorted({t for _, t in f["bl_edges"] if t in self.functions})
            fn_list.append({
                "root": r,
                "nodes": len(nodes),
                "lo": min(nodes),
                "hi": max(nodes),
                "callees": callees,
            })
        by_root = {e["root"]: e for e in fn_list}
        for e in fn_list:
            e["callers"] = sorted(
                c["root"] for c in fn_list
                if e["root"] in c["callees"]
            )

        reached_bytes = set()
        for f in self.functions.values():
            for a in f["nodes"]:
                reached_bytes.add(a - self.base)
        coverage = len(reached_bytes) / len(self.image) * 100 if self.image else 0.0

        return {
            "image_size": len(self.image),
            "candidate_roots": len(self.root_status),
            "confirmed_functions": len(fn_list),
            "coverage_bytes": len(reached_bytes),
            "coverage_pct": coverage,
            "rejected": [{"root": r, "reason": reason}
                         for r, (ok, reason) in self.root_status.items() if not ok],
            "functions": fn_list,
        }

    def walk_print(self, root: int):
        reached, bl_edges, br_edges, complete = self._walk(root)
        print(f"walk of {root:08x}: {len(reached)} nodes, complete={complete}")
        edge_map = {}
        for (a, t) in bl_edges:
            edge_map.setdefault(a, []).append(("bl", t))
        for (a, t) in br_edges:
            edge_map.setdefault(a, []).append(("br", t))
        for a in sorted(reached):
            insn = self._decode(a)
            if insn is None:
                continue
            mark = "".join(f"  {kind}->{t:08x}" for (kind, t) in edge_map.get(a, []))
            print(f"  {a:08x}: {insn.mnemonic:8s} {insn.op_str}{mark}")
        return 0

    # ---- peripheral register scanner (Step 2) --------------------------
    USART1_OFF = {
        0x00: "CR1", 0x04: "CR2", 0x08: "CR3", 0x0C: "BRR", 0x10: "GTPR",
        0x1C: "ISR", 0x20: "ICR", 0x24: "RDR", 0x28: "TDR",
    }

    def _build_reg(self, insn):
        """Register written by a mov.w/movw; else None."""
        if insn.mnemonic not in ("mov.w", "movw", "mov"):
            return None
        if "#" not in insn.op_str:
            return None
        return insn.op_str.split(",")[0].strip()

    def _imm_val(self, insn):
        if "#" not in insn.op_str:
            return None
        try:
            return int(insn.op_str.split("#")[1].split(",")[0].strip(), 16)
        except ValueError:
            return None

    def scan_periph(self, periph: int, window: int = 40):
        """Find constructions of `periph` base and the accesses that follow.

        Step 2 of the roadmap: given a peripheral base (e.g. USART1
        0x40013800), locate every 'mov.w/movw #lo ; movt #hi' pair that builds
        it, then linearly scan forward (bounded by `window` instructions) for
        `[reg,#offset]` accesses using that base register, classifying each
        offset. Also lists whether the construction falls inside a
        CFG-confirmed function. Linear + windowed because the image interleaves
        data (see firmware.md), so results are candidates for human review.
        """
        lo16, hi16 = periph & 0xFFFF, (periph >> 16) & 0xFFFF
        sites = []
        insns = self._linear()
        for i, insn in enumerate(insns):
            reg = self._build_reg(insn)
            if reg is None or self._imm_val(insn) != lo16:
                continue
            # look ahead a couple insns for the matching movt
            for j in range(i + 1, min(i + 4, len(insns))):
                nj = insns[j]
                if (nj.mnemonic == "movt"
                        and nj.op_str.split(",")[0].strip() == reg
                        and self._imm_val(nj) == hi16):
                    hits = []       # (insn_addr, mnemonic, op, offset, rw)
                    # forward scan for accesses with this base register
                    for k in range(j + 1, min(j + 1 + window, len(insns))):
                        nk = insns[k]
                        op = nk.op_str.replace(" ", "")
                        # match [reg,#off] with a fixed offset
                        markers = [(o, "w") for o in ("str", "strb", "strh")]
                        markers += [(o, "r") for o in ("ldr", "ldrb", "ldrh", "ldr.w")]
                        for mn, rw in markers:
                            if nk.mnemonic != mn:
                                continue
                            off = None
                            if "[%s,#" % reg in op:
                                off = self._extract_off(op, reg)
                            elif nk.op_str.strip().endswith("[%s]" % reg):
                                off = 0     # [reg] == offset 0 (e.g. USART CR1)
                            if off is not None and off in self.USART1_OFF:
                                hits.append((nk.addr, nk.mnemonic,
                                             nk.op_str, off, rw))
                                break
                    # reachable? construction inside any confirmed fn range
                    in_fn = any(
                        (f["nodes"] and min(f["nodes"]) <= insn.addr <= max(f["nodes"]))
                        for f in self.functions.values())
                    sites.append({
                        "periph": periph,
                        "base": insn.addr,
                        "reg": reg,
                        "confirmed": in_fn,
                        "accesses": [{"addr": a, "mnemonic": m, "ops": o,
                                      "offset": off, "reg": self.USART1_OFF[off],
                                      "rw": rw} for (a, m, o, off, rw) in hits],
                    })
                    break
        return sites

    def _extract_off(self, op, reg):
        """Parse the numeric offset from '[reg,#0xNN]'."""
        try:
            sub = op.split("[%s,#" % reg)[1].split("]")[0]
            return int(sub, 16)
        except (IndexError, ValueError):
            return None

    def _linear(self):
        """Single-pass linear decode of the whole image (candidate census)."""
        insns = []
        for off in range(0, len(self.image) - 3, 2):
            insn = self._decode(self.base + off)
            if insn is not None:
                insns.append(insn)
        return insns


def load_image(path: Path) -> bytes:
    frames = parse_frames(path)
    if not frames:
        raise ValueError(f"{path}: no firmware frames")
    max_a = max(a for a, _ in frames)
    return b"".join(unpack7(p) for a, p in sorted(frames) if a != max_a)


def _print_periph(sites):
    if not sites:
        print("\nno constructions of that peripheral base found")
        return 0
    print("\nperipheral base construction sites:")
    for s in sites:
        tag = "in-confirmed-fn" if s["confirmed"] else "not-in-confirmed-fn"
        print(f"  base {s['base']:08x}: reg {s['reg']}  [{tag}]")
        if not s["accesses"]:
            print("      (no register accesses found in window)")
        for a in s["accesses"]:
            print(f"      {a['addr']:08x}: {a['mnemonic']:6s} {a['ops']:22s} "
                  f"= {a['reg']:4s} ({a['rw']})")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="fw_cfg.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("syx", help="official .syx firmware update file")
    ap.add_argument("--json", dest="json_out", help="write function map + call graph JSON")
    ap.add_argument("--limit", type=int, help="cap candidate roots processed")
    ap.add_argument("--seed", action="append", type=lambda x: int(x, 0),
                    default=[], help="extra root address (flash space)")
    ap.add_argument("--walk", type=lambda x: int(x, 0), help="walk one address and print edges")
    ap.add_argument("--periph", type=lambda x: int(x, 0),
                    help="peripheral base to scan (e.g. 0x40013800 USART1); "
                         "finds base constructions + register accesses and exits")
    args = ap.parse_args(argv)

    image = load_image(Path(args.syx))
    print(f"{Path(args.syx).name}: image {len(image)} bytes  base {FLASH_BASE:08x}")
    b = CfgBuilder(image)

    if args.walk is not None:
        return b.walk_print(args.walk)

    if args.periph is not None:
        _ = b.analyze(seeds=args.seed, limit=args.limit)  # for reachability
        return _print_periph(b.scan_periph(args.periph))

    report = b.analyze(seeds=args.seed, limit=args.limit)
    print(f"\ncandidate roots      : {report['candidate_roots']}")
    print(f"confirmed functions  : {report['confirmed_functions']}")
    print(f"code coverage        : {report['coverage_bytes']} / {report['image_size']} bytes "
          f"({report['coverage_pct']:.1f}%)")
    print(f"rejected (data?)     : {len(report['rejected'])}")
    print("\nconfirmed functions (root, lo-hi, nodes, callees, callers):")
    for f in sorted(report["functions"], key=lambda x: x["root"]):
        print(f"  {f['root']:08x}  [{f['lo']:08x}-{f['hi']:08x}]  n={f['nodes']:4d}  "
              f"callees={len(f['callees']):3d}  callers={len(f['callers']):3d}")
    if report["rejected"]:
        print("\nrejected roots (top, suspected data):")
        for r in report["rejected"][:25]:
            print(f"  {r['root']:08x}  {r['reason']}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2))
        print(f"\nwrote: {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
