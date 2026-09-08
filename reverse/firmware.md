# MFB Tanzmaus — Firmware Update Protocol

Reverse-engineered from the four [MFB OS update files](../mfb/firmware/)

| Version | Data frames¹ | Final frame² | Header addr | Image bytes |
|---|---|---|---|---|
| 1.6 | 3382 | 48 B @ addr 3383 | 0x0D38 (3384) | 111,638 |
| 1.61 | 3391 | 38 B @ addr 3392 | 0x0D41 (3393) | 111,926 |
| 1.62 | 3414 | 29 B @ addr 3415 | 0x0D58 (3416) | 112,677 |
| 1.63 | 3416 | 29 B @ addr 3417 | 0x0D5A (3418) | 112,743 |

¹ full 52-byte data frames, addr 1..N-2
² the last data frame (addr N-1) is shorter — the image is not 33-byte aligned; carries the image tail; no checksum field.

| File | Contents |
|---|---|
| `fw_cksum.py` | Embeds the 21-bit XOR-linear checksum weight tables and verifies every frame across all four firmware versions. |
| `fw_decoder.py` | Unpacks 7-bit MIDI-safe payload bytes back to 8-bit and reconstructs the firmware image. Verifies address contiguity and every 3-byte checksum. |
| `fw_disasm.py` | Disassembles the decoded image to confirm the Cortex-M (Thumb-2) code. |
| `fw_dispatcher.py` | Heuristic SysEx analysis: single-pass decode, vector-table scan, peripheral-constant reconstruction, access-map classification, command inventory. See the [SysEx reply-probe runbook](sysex-probes.md). |
| `fw_trailer.py` | Decodes the final (short) frame = the image tail: unpacks and disassembles it, lists embedded SRAM/flash words, and reports image-level checksums (global-signature checks returned negative). |
| `fw_ramxref.py` | Raw byte-occurrence scan (decode-noise immune) plus `movw`/`movt`-adjacency and literal-pool inventory for the SRAM / peripheral addresses the app references. |
| `fw_cfg.py` | Recursive-descent Thumb-2 control-flow analysis (see [Control-flow graph](#control-flow-graph) below). Builds a CFG from candidate roots, validates prologue-backed function starts, and reports the call graph and coverage. `--periph=<base>` runs the peripheral-access scanner (see [USART1 access classification](#usart1-access-classification)). |
| `fw_dump_parse.py` | SPI DataFlash dump parser (see [Static-analysis findings](#static-analysis-findings) below). Identifies the part/density from a JEDEC RDID response (`--jedec=HEX`), or analyzes a raw dump: page-geometry heuristics, 12-bit sample evidence, data-region mapping, slot-capacity scan. For SOIC-8 clip + `ch341a_spi` dump recovery (see [pcb-visual-analysis.md](pcb-visual-analysis.md)). |

---

## Delivery

A `.syx` is one sequential SysEx session of **N cmd-01 frames with contiguous addresses 1..N**:
- addr **1..N-2**: full **52-byte data frames**,
- addr **N-1**: the **final (short) data frame** — the image tail, 29–48 bytes, no checksum field,
- addr **N**: the **metadata header** frame (52 bytes), its address equals the total frame count N.

Shared shell: `F0 00 21 0B 04 00 01` (MFB SysEx header, device ID `0x0B`, cmd `0x01`).

| Segment | Length | Count |
|---|---|---|
| Data frames | 52 bytes | N-2 |
| Final (image tail) | 29–48 bytes | 1 |
| Metadata header | 52 bytes | 1 |

Data-frame layout (52 bytes):

```
F0  00 21 0B 04 00  01  00  addrHi addrLo  [38 payload]  ck0 ck1 ck2  F7
```

| Byte(s) | Field | Notes |
|---|---|---|
| 6 | cmd | `0x01` firmware upload |
| 7 | reserved | always `0x00` (padding before the address) |
| 8–9 | address | big-endian, both bytes 7-bit: `addrHi<<7 \| addrLo`, contiguous 1..N |
| 10–47 | payload | 38 bytes of 7-bit-safe firmware data |
| 48–50 | checksum | 21-bit XOR-linear code (see Checksums) |

### Metadata header frame

Addr N = total frame count (sentinel), two past the last data-frame address. Carries version/signature metadata.

| Version | Header addr (== total frames) | Signature bytes `data[10:24]` |
|---|---|---|
| 1.6 | 0x0D38 (3384) | `00 00 70 7c 06 20 00 52 7c 01 00 00 00 00` |
| 1.61 | 0x0D41 (3393) | `00 00 3c 60 0b 20 00 53 14 00 00 00 00 00` |
| 1.62 | 0x0D58 (3416) | `00 00 54 73 0f 20 00 54 6c 01 00 00 00 00` |
| 1.63 | 0x0D5A (3418) | `00 00 10 2f 09 20 40 54 2c 00 00 00 00 00` |

The signature fields differ per version (version/build/checksum encoding) and are zero-padded; the exact encoding is undetermined.

V1.61 header frame, field-by-field:
```
F0  00 21 0B 04 00  01  00  1a 41  00 00 3c 60 0b 20 00 53 14 ... 00 01  1f 01 2a  F7
```
- address `0x1A41` = `(0x1A<<7)|0x41` = 3393 = 3391 data + final (image tail) + header
- `data[0:16]` = `00 00 3c 60 0b 20 00 53 14 00 00 00 00 00 00 ...` signature
- data tail `00 01` = end marker; checksum = `1f 01 2a`

### Final frame — image tail

The final data frame (addr N−1) is shorter than 52 bytes (image not 33-byte aligned) — the last image chunk, no checksum field. Unpacked with the same LSB-first 7→8 rule, it yields the end of the flash image — a small Thumb-2 routine (`70 47` = `bx lr`) followed by 4-byte-aligned RAM words that are stable across all four versions:

| Version | Frame len | Unpacked tail (bytes) |
|---|---|---|
| 1.6 | 48 | `11 12` + `str r2,[r3,#4] · ldr r0,[r3,#4] · ldr r1,[r3] · adds r2,r0,#1 · eor r0,r2,r1,lsr#8 · str r0,[r3,#4] · bx lr` + `65 01 00 20` `bc 00 00 20` `80 40 37 10` |
| 1.61 | 38 | `adds r2,r0,#1 · eor r0,r2,r1,lsr#8 · str r0,[r3,#4] · bx lr` + `65 01 00 20` `bc 00 00 20` `02 5f 00` |
| 1.62 | 29 | `bx lr` + `61 01 00 20` `bc 00 00 20` `00 f8 80` |
| 1.63 | 29 | `bx lr` + `61 01 00 20` `bc 00 00 20` `00 f0 81` |

The words (LE, so `65 01 00 20` = `0x20000165`) are **`0x20000165`** (V1.6/1.61) or **`0x20000161`** (V1.62/1.63) plus **`0x200000bc`** in every version. 4-byte aligned, sit at the very end of the image, and byte-occurrence scans show the app never references them (each appears exactly once per image) — a small metadata/boot footer, consumed by the update mechanism. The app *does* reference nearby low-SRAM addresses heavily: V1.62/1.63 use `0x20000164` (16 occurrences) and `0x200000cc` (13), V1.6/1.61 different low-SRAM words (`0x200000da`, `0x2000013e`, …) — the RAM layout shifts between versions.

Image-level checksums (CRC32 / CRC-16-CRC_HQX / XOR8 / SUM8 over the image body) do **not** match any tail word: the tail is not a global image signature.

---

## Reconstructing the image

The 38 payload bytes are **not** raw data — they are MIDI-safe (7-bit) and must be re-packed to 8-bit, **LSB-first**, **per frame** (reset the accumulator each frame), then concatenated **in address order**, excluding only the metadata header frame (addr N). Image base is `0x08000000` (STM32F303 flash origin).

```
per frame: acc |= (byte & 0x7f) << nb; nb += 7; emit a byte when nb >= 8
```

Image sizes are listed above (all < 256 KB flash). The first ~0x62 bytes are zero (frames 1–3). The final frame, unpacked alone, yields genuine Cortex-M Thumb-2 code (`70 47` = `bx lr`) — confirming the transform is correct.

---

## Hardware

The MCU is an **STM32F303CCT6** (Cortex-M4F, 256 KB flash, 40 KB SRAM). The initial stack-pointer sentinel `0x2000a000` equals exactly `0x20000000 + 40 KB` (SRAM top), confirming the decode and the memory map.

## Image layout

`fw_dispatcher.py` reads a vector table at image offset **`0x1ef`** with a compact set of entries (**see resolution below**):

| Index | Word | Meaning |
|---|---|---|
| 0 | `0x2000a000` | Initial SP = SRAM top |
| 1 | reset vector | grows per version (V1.6: `0x08012fc5`) |
| 2–6 | shared handler / faults (`0x08013039`) | |
| 7–10 | `0` | reserved, not populated |

The reset handler disassembles to coherent Cortex-M init code (nibble `cmp #0xf` parameter-zeroing loops, `pop {r3, pc}` epilogues). The image has a short **0x62-byte** leading zero prefix (frames 1..~3 carry all-zero payloads) before genuine code; `0x2000a000` appears exactly once in the image (the SRAM-top sentinel).

### Resolution (T2a)

`0x1ef` is **not 4-aligned**, which rules out a hardware vector table — the block (`{0x2000a000, 0x08012fc5, repeated 0x08013039}`) is a **boot-handoff manifest** read by the separate bootloader, and the app itself is **fully polled** (no VTOR write, no NVIC table; SCB `0xE000ED00` used only for an AIRCR priority-grouping store). See [Update bootloader](#update-bootloader) below for the full model.

---

## Control-flow graph

`fw_cfg.py` builds a real recursive-descent Thumb-2 CFG, replacing the linear sweep of `fw_dispatcher.py`. No single trustworthy entry point (no vector table; the `0x1ef` manifest's reset word `0x08012fc5` disassembles to a mid-function tail), so it seeds from many candidate roots and validates each:

- **Candidate roots**: every constant `bl`/`blx` target from an initial linear decode, every `push {..,lr}` prologue site, plus explicit `--seed=` addresses.
- **Recursive descent**: follows only real branch edges (fall-through, conditional/unconditional `b`, `cbz`/`cbnz`, IT blocks) and stops at returns (`bx lr`, `pop {..,pc}`) or undecodable data. Calls (`bl`) are recorded as edges but not inlined, keeping each function body compact.
- **Validation**: a root is a *confirmed function* only if it begins with a real prologue (`push {..,lr}`), reaches at least one return, and its reachable node set is locally dense. The other ~97% of linear-decode `bl` targets come from data masquerading as code and are rejected.
- **Outputs**: function map (root, low/high, node count, callees, callers), call graph, and code coverage, as console text or `--json`.

Usage on V1.63:

```sh
# full analysis (all V1.63 roots), JSON out  (run from reverse/firmware-scripts/)
fw_cfg.py ../../mfb/firmware/Tanzmaus_v1_63.syx --json=cfg-63.json
# walk one address and print its branch edges
fw_cfg.py ../../mfb/firmware/Tanzmaus_v1_63.syx --walk=0x08011012
```

### Result and interpretation

On V1.63: **340 candidate roots → 11 prologue-backed functions, ~1.2% image coverage**. Walk of the confirmed root `0x08011012` (`push {r3,r4,r5,lr}`) shows a genuine function start (`ldrb`/`cmp #0` guard), and the documented USART1 base-construction site `0x08010e7a` lands inside this function's range — **reachability analysis reaches real code**.

But every confirmed root quickly bleeds into adjacent data via unresolved indirect/switch branches (`blx rX`, computed `b`), so no single function body isolates cleanly. Expected negative result: the app is not a set of cleanly-delineated, singly-rooted functions, consistent with the fully-polled / bootloader-handoff model. Resolving the switch/indirect branch tables and the true hand-off entry is not achievable from the shipped `.syx` alone — it points back to the hardware routes in `to-do.md` (full flash dump via BOOT0, and the separate bootloader).

---

## USART1 access classification

`fw_cfg.py --periph=0x40013800` finds every base construction of USART1 (`mov.w/movw #0x3800 ; movt #0x4001`) and, within a local window, classifies the `[reg,#offset]` accesses that follow. Targeted scan isolates genuine USART1 traffic; the raw image is awash in `+0x24`/`+0x28` GPIO accesses (`GPIOx->AFRH`/`GPIOx->BRR`, see [Empirical probes](#empirical-probes)).

STM32F303 USART register offsets used (this confirms register identity, not just a bare address): `CR1 +0x00`, `CR2 +0x04`, `CR3 +0x08`, `BRR +0x0C`, `ISR +0x1C`, `RDR +0x24`, `TDR +0x28`.

| Version | construction | accesses | role |
|---|---|---|---|
| V1.6 | `0x080112e0` (r3) | `ldrh [r3,#0x24]`=**RDR read**, `uxtb` extr. byte; `ldrb/strb [r3,#8]`=**CR3** read-modify-write | RX data read + CR3 toggle |
| V1.61 | — | base not built via a direct movw/movt pair (no 0x3800/0x4001 immediate, no BE literal `0x40013800`); construction differs | unclassified |
| V1.62 | `0x08010e7a` (r3); RX `0x08012742` (r2) | init: `str [r3]`=**CR1**, `str [r3,#8]`=**CR3**, `strh [r3,#0xc]`=**BRR**; RX: `ldr [r2,#0x1c]`=**ISR** | init + ISR poll |
| V1.63 | `0x08010e7a` (r3, in confirmed fn `0x08011012`); RX `0x08012784` (r2) | init: **CR1/CR3/BRR** writes; RX: `ldr [r2,#0x1c]`=**ISR** | init + ISR poll |

Init (V1.62/1.63 `0x08010e7a`):

```asm
mov.w  r3, #0x3800      ; r3 = USART1 (0x40013800)
movt   r3, #0x4001
str    r1, [r3]         ; CR1  <- enable value
str    r1, [r3, #8]     ; CR3
mov.w  r1, #0x900
strh   r1, [r3, #0xc]   ; BRR  <- 0x900 = 2304 = 72 MHz / 31,250 baud
```

**BRR = `0x900` ⇒ 31,250 baud = MIDI** (APB2 72 MHz ÷ 2304), confirming USART1 = the MIDI UART.

RX/ISR poll (V1.63 `0x08012784`):

```asm
mov.w  r2, #0x3800      ; r2 = USART1
movt   r2, #0x4001
ldr    r3, [r2, #0x1c]  ; read ISR
lsls   r3, r3, #0x18    ; test ISR bit 7 (TXE on F303)
bpl    <end>            ; bit clear -> re-enable IRQ, return
...                     ; set -> proceed (cpsid i, then handshake/read)
```

Caveat on the flag bit: the ISR test at `0x08012784` shifts by `#0x18` (bit 7). On the STM32F303 USART, ISR bit 7 is **TXE** (transmit-empty) and bit 5 is RXNE; so this site is best read as a *TX-ready* check, i.e. the transmit path. The unambiguous *receive* read is V1.6's `ldrh [USART1,#0x24]` (RDR) with a `uxtb` byte-extract (data push to a buffer) at `0x080112e0`. Fall-through past the poll hits interleaved data — the full handshake/byte-consumption loop is not statically recoverable. USART1 is polled (no IRQ vectoring of MIDI bytes), matching the fully-polled model. Verified sites: `0x08010e7a` (init), `0x08012742`/`0x08012784` (ISR poll), V1.6 `0x080112e0` (RDR read).

---

## Static-analysis findings

Cross-checked against the host-side sample-tool source and the repo SysEx documentation. All are candidates — the image interleaves data, so boundaries are untested, and each records its confidence honestly. Items covered elsewhere in this file (SPI1/DataFlash `0x40013000`, the `0x1EF` bootloader-manifest finding, the GPIO `+0x24`/`+0x28` false-USART caveat) are linked, not duplicated.

### Sample SysEx decode path — genuine executable function, reachability unproven

An aligned Thumb-2 disassembly confirms `0x08011D76` is a **real compiled function** (genuine `push.w {r4..lr}` prologue at `0x08011D76`, `r7 = r0` caller buffer, `sub sp,#0xc`, clean `pop.w {...,pc}` tail at `0x08011E2E`), not a linear-sweep false positive. Its body matches the documented sample packet format exactly: reads the byte at offset `+0x3A`, `movs r1,#0x39` (57-byte CRC input), streams `r6=r7+0x0A`/`r5=r7+0x0B`, a two-byte loop terminating at `cmp r3,#0x30` (48-byte payload = 24 samples), `orr.w r2,r2,r10,lsl #7` (`lo | hi<<7` reconstruction), and `ubfx ...,#8,#4` (12-bit extract). CRC7 primitive also present (below). **Reachability is the only open point**: no direct `BL`/`BLX` immediate anywhere targets `0x08011D76` (or `±1`), so it is reached via an indirect dispatch/jump table, a wrapper, or is dead/unreferenced compiled code — do not assume it is wired to the live SysEx receiver until a reachable control-flow path is proven.

### MIDI/SysEx-shaped code region at `0x08011736` — pattern verified, role unproven

An aligned Thumb-2 decode of `0x08011736` shows a coherent status-classification fragment: `ldrh r0,[r3,#0x24]` plus byte-extract, tests against `0xEF` (`b`/`cc` selector), `0xB0` (control change), and `0xF0` (SysEx); a `cmp r2,#0xF7` SysEx-termination check; and a real-time `F8–FC` dispatch via `ldr.w pc,[table]` with `pop.w {...,pc}` at `0x080117BE`. Verified verbatim against the binary. **Honest caveat**: the `+0x24` read is USART1 `RDR` *only if* `r3` holds `0x40013800`, but no `movw/movt` construction of USART1 precedes it in the surrounding (data-interleaved) linear code, and `0x08011736` is not one of the two confirmed USART1 base-construction sites — so the **MIDI-receiver/RDR interpretation is unproven**, a candidate for a reachable-CFG follow-up rather than an accepted parser.

### Thumb TBB/TBH switch census — verified

V1.63 contains exactly **18** Thumb table-branch instructions (`tbb`/`tbh`). Sites resolve to in-flash targets conservatively (bounded by a preceding `cmp #N`, `FW_CFG` validates all case targets, no fall-through — see `fw_cfg.py`). Six resolve to coherent, walkable targets: `0x080046FA`, `0x08006A04`, `0x08007450`, `0x080088F0`, `0x0800B02A`, `0x0800CAEE`. Three resolve to in-flash targets but fail walk coherence and are treated as data/false positives: `0x08010C28`, `0x0800F2F8`, `0x0801090C`. A raw table-branch opcode alone is not evidence of a switch; it must be bounded and coherent.

### CRC7 primitive — strong, unresolved boundary

Around `0x08000C6C–0x08000CF8` the instructions contain the distinctive operations of the documented CRC7 transform: `0x80` testing, conditional XOR `0x09`, `0x78` masking, shift/XOR mixing, and final `0x7F` masking. Strong evidence for the CRC7 primitive, embedded in a larger/mixed region; exact function boundary unproven, message-level CRC validation path unresolved.

### Sample storage geometry — high confidence region, zero references

At `0x0801A230` a data cluster holds the sample-tool storage geometry values `0`, `728`, `2184`, `3640`, `91`, `182`, `364`; nearby at `0x0801A248` are misaligned 16-bit constants: `0x55F0` (22000), `0xABE0` (44000), `0x157C0` (88000), verified against the decoded V1.63 image. Confidence **high**.

**Zero static references** (proved on the decoded V1.63 image): no 32-bit LE literal `0x0801A230` anywhere, no `movw`/`movt` pair constructing `0x0801A2xx`, and no raw LE32 pattern pointing into `0x0801A200–0x0801B8FF` (this image addresses flash through PC-relative literal pools, so that scan is the right check). The single `movw`/`movt` pair yielding a flash address from the whole-image scan resolves to `0x0801DE90`, **beyond the image end** (`0x0801B867`) — a mid-data misdecode, not a reference.

**Synced to the host tool, and the arithmetic is host-side**: the exact same geometry lives in `mfb/tool/TanzmausSampleTool/Source/TanzmausSampleTool.cpp` (lines ~279–292) and `crc7.cpp::AddPage`:

- `sampleNo < 4`: `sampleSize = 22000`, `START_ADDR = ((sampleDest*4)+sampleNo)*91`
- `sampleNo < 12`: `sampleSize = 44000`, `START_ADDR = 728 + ((sampleDest*8)+(sampleNo-4))*182`
- `sampleNo >= 12`: `sampleSize = 88000`, `START_ADDR = 3640 + ((sampleDest*4)+(sampleNo-12))*364`
- data transmitted as 264-sample pages; `AddPage` sends a 14-bit page address (`lo = PAGE_ADDR&0x7f`, `hi = (PAGE_ADDR>>7)&0x7f`) in frame bytes 6–7.

So the device **receives** pre-computed page addresses and has no reason to multiply by 91/182/364. Confirmed: the whole image contains **no** `movw` of `91/182/364/728/3640/22000/44000/88000` and no arithmetic on those immediates — a search for a firmware `n*91` consumer is futile. The `0x0801A230` cluster is best read as a capacity/layout LUT (e.g. per-slot page-count or boundary table for validation), whose consumer — if any — is still unproven.

### Sample representation

Host-side protocol sends each sample as two 7-bit bytes; host conversion yields a 12-bit unsigned value; the firmware candidate reconstructs a 14-bit MIDI-safe word via `lo | hi<<7`. **Do not conflate** the 14-bit transport representation with the 12-bit useful sample range.

### Page size — resolved

The sample protocol groups `11 × 24 = 264` samples/page × 2 bytes = **528 bytes**. This matches the **default page size** of the shipped DataFlash parts — AT45DB321E (528 B) and AT45DB081E (264 B) — see [pcb-datasheet-AT45DB321E.md](pcb-datasheet-AT45DB321E.md). The physical page size hypothesis is confirmed against the chip markings.

### Audio path — consistent, not proven

A site constructs DAC base `0x40007400` (movw/movt; no literal pool) and `0x0FFF` saturation appears in executable-looking code — consistent with a 12-bit audio path. This does not prove the saturation routine is sample playback; playback buffer, timer/DMA path, DAC register writes, and voice scheduler remain unresolved.

---

## Checksums

### 3-byte checksum (bytes 48–50) — RECOVERED

A **21-bit XOR-linear (GF(2)) code** over the 16-bit frame **address** and **all 38 payload bytes** (including col36/37). Verified **0 mismatches over 13,607 frames** — all full 52-byte data frames plus the four metadata header frames across the four versions (the short final frames carry no checksum field and are excluded).

- Same (address, payload) ⇒ same checksum — 0 conflicts over 10,675 keys.
- The middle byte is always `0x00`/`0x01` — it carries the high bit of the 21-bit word; bytes 0 and 2 carry the bulk.
- Not a standard CRC-16/CRC-8 (common polynomials brute-forced, no match) — a proprietary linear code.
- Payload bytes contribute only their 7 low bits (bit 7 = 0); address uses bits 0–15.
- Per-bit 21-bit weight tables are embedded in `reverse/firmware-scripts/fw_cksum.py` (`ADDR_BITS`, `PAYLOAD`).

For all-zero data the checksum depends only on the address, e.g. `addr 0x0001 → 4d 00 78`, `0x0002 → 57 01 48`, `0x0004 → 62 01 28`, `0x0007 → 78 00 18`.

```
value = XOR_{addr bit b set}  ADDR_BITS[b]
      ^ XOR_{byte k, bit b set} PAYLOAD[k][b]      k=0..37, b=0..6

checksum bytes:  ck[i] = (value >> 7*i) & 0x7F
```

This checksum is the value needed to originate valid firmware frames.

### Columns 46 & 47 — packing tail, not a checksum — RESOLVED

The earlier "5-bit field at columns 36/37" was a **column-misindexing artifact**. Verification on the decoded bytes:

- **Columns 36/37 (frame bytes 36/37) are plain 7-bit image bytes** — bit-scan across all four firmware versions shows values spanning the full `0..0x7F` range. They are packed into chunk bytes 22–25 of the image like any other data.
- The small 5-bit field actually lives one frame byte-group later, at the **PAYLOAD tail (frame bytes 46/47)**. With `ch = unpack7(payload)` (33 bytes):

```
pay36[0..3] = ch[31] >> 4        (image byte 31, high nibble)
pay36[4..6] = ch[32] & 0x07      (image byte 32, low 3 bits)
pay37       = (ch[32] >> 3) & 0x1F
```

Verified **0 mismatches over 13,607 full frames** (all four versions). So `pay[37]` in practice is `0`/`1` and `pay[36]` is `0..15`, i.e. the transmitted tail is a fixed re-encoding of the last two packed chunk bytes — NOT an independent checksum. No per-frame transmitter state exists beyond this.

- Related image-structure finding: for every full frame, `ch[32]` ∈ {`0x00`, `0x08`} (3,382 positions verified → `image[33*k+32]` ∈ {0,8}). The value is data-dependent (not address parity or a checksum function) — it is a per-frame staging byte the host upload tool places in the image stream, of unknown but uncompromising semantics. It does NOT gate frame origination (any `0x00`/`0x08` value in the image reproduces the transmitted tail). Its meaning (e.g. a firmware-side flag/state byte) is unresolved; it is not needed to originate valid frames.

**Consequence:** to originate valid frames you only need the solved 3-byte checksum — there is no secondary 5-bit field to compute.

---

## Update bootloader

The app image contains **no flash-programming code**: no F303 FLASH unlock keys (`0x45670123`/`0xcdef89ab`), no writes to `FLASH->CR`/`KEYR`, no SysEx OS-receive path. Startup only does standard init (SCB->AIRCR priority group, RCC clock enables).

The OS-update receive/validate/flash logic therefore lives in a **separate bootloader not shipped in the `.syx`**; the file carries only the application image (whose last 4-byte-aligned words — the `0x20000161`/`0x20000165` + `0x200000bc` footer — are plausibly the hand-off data the bootloader reads). Update code not recoverable from shipped artifacts.

Scan results agree with a **separate-bootloader model**:
- the app has **no vector-table or VTOR write**; its only use of `0xE000ED00` (SCB) is a single **AIRCR priority-grouping** store (`0x05FA0000 | group`). The design is **fully polled** (no NVIC vector table, no interrupts in app);
- the odd-aligned block at image offset `0x1ef` (`{0x2000a000, 0x08012fc5, repeated 0x08013039}`) is the **boot-handoff manifest** a separate bootloader reads — its alignment (≠ `n*4`, words ≠ 16-bit halfword expansion) rules out an NVIC table;
- all four versions construct the same **peripheral bases via `movw &0xffff` /
  `movt &0xffff0000` pairs** with a uniform low code (`0x080004E0`-family):

  | Peripheral | Address |
  |---|---|
  | TIM3 | `0x40000400` |
  | TIM4 | `0x40000800` |
  | TIM6 | `0x40001000` |
  | TIM7 | `0x40001400` |
  | EXTI | `0x40010400` |
  | SPI1 | `0x40013000` |
  | USART1 | `0x40013800` |
  | TIM15 | `0x40014000` |
  | TIM16 | `0x40014400` |
  | TIM17 | `0x40014800` |
  | RCC | `0x40021000` |
  | FLASH | `0x40022000` |
  | GPIOB | `0x48000400` |
  | GPIOC | `0x48000800` |
  | GPIOE | `0x48001000` |
- **USART1 = the MIDI UART** (resolved): V1.6 builds the TDR address `0x40013828` directly (`0x8010a58`), V1.62/63 the base (`0x8010e7a`); **BRR = `0x900` ⇒ 72 MHz/2304 = 31,250 baud = MIDI**; init writes CR1/CR3 only.
- **SPI1 = the Adesto DataFlash driver** (resolved): identical construction at `0x080005F2`/`0x0800077A` in all versions; CR1 writes `0x3010`/`0x3080`, status polling via `SPI1->SR` masks `0x80` (`SPIF`) and `0x600` (`MODF`/`OVR`). This is the sample-storage read/write path (two SPI DataFlash chips on the PCB).

### Could a DataFlash chip hold the bootloader? — assessed, unlikely

Hypothesis: one of the two Adesto chips (rather than internal flash) carries the OS-update bootloader. Evidence weighs against it:

- **Capacity**: a fully loaded bank is 16 slots = 792,000 samples × 2 B = **1,584,000 B**; both banks = **3,168,000 B**. The 32-Mbit AT45DB321E holds 4,194,304 B (enough for both banks, ~1 MB spare), the 8-Mbit AT45DB081E holds 1,048,576 B (less than one bank). Both chips are therefore consumed by sample storage (SP1/SP2) with little or nothing left claiming a bootloader role. See [pcb-datasheet-AT45DB321E.md](pcb-datasheet-AT45DB321E.md).
- **No XIP**: the Cortex-M4F cannot execute directly from the SPI DataFlash (no memory-mapped/QSPI XIP on the F303 data bus, per `pcb-datasheet-STM32F303CCT6.md`). A DataFlash-resident bootloader would have to be copied to RAM and jumped to, an architecture the app's scan results give no hint of.
- **Recovery routes assume internal flash**: `to-do.md` §3 recovers the firmware via **BOOT0 strap + ST ROM USART loader** — i.e. internal flash. If the bootloader lived on SPI flash that path would be moot.

It is **not fully excluded** without reading the chips; the dumped content would settle it. `fw_dump_parse.py` now classifies each dump (7-bit sample-consistent vs. data-heavy/binary) and flags a non-sample region at flash start as a possible bootloader/config store.

---

## Device ID

`0x0B` is constant across every official firmware image: the device ID is hardcoded and two chained Tanzmauses cannot be addressed individually.

## Empirical probes

Whether the Tanzmaus ever **transmits** SysEx in response to a received message (identity / handshake / reply) is answered empirically in [sysex-probes.md](sysex-probes.md). Answer: **fire-and-forget** — the firmware never replies.

(V1.63, via `fw_dispatcher.py`): the image disassembles fully (49,832 Thumb-2 instructions) with genuine code from near the image start; movw/movt + offset addressing with **no 32-bit peripheral literal pools** for RCC/USART/GPIO. The access pattern clustered at `0x080003B6..0x0800234A` previously flagged as USART TDR/RDR (`+0x28`/`+0x24`) is actually **GPIO** (addressing `GPIOx->AFRH` at `+0x24` and `GPIOx->BRR` at `+0x28`, e.g. `mov.w r6,#0x400; movt r6,#0x4800; strh r5,[r6,#0x28]` = GPIOB->BRR → 74HC595 LED latch). A true `cmp #0xF0` (SysEx `F0`) site exists. The main remaining unknowns — the full RX command set — are best answered empirically.

---

## Remaining unknowns

- Meaning of the header signature fields and of the final-frame footer words (`0x20000161`/`0x20000165` + `0x200000bc`), and of the low-SRAM addresses the app itself builds/reads (`0x20000164`, `0x200000cc` in V1.62/1.63).
- Meaning of `image[33*k+32] ∈ {0x00, 0x08}` (the per-frame tail byte the host tool writes). Not needed to originate frames; may be a firmware-side flag/state byte.
- Whether the bootloader flashes the whole 256 KB or only the app region (needs on-device/bootloader access). Its host location (internal flash vs. a DataFlash chip) is assessed [above](#could-a-dataflash-chip-hold-the-bootloader--assessed-unlikely) — see the chip dumps (`to-do.md` §2/§3) to settle it.
- The app's true entry point / how the separate bootloader jumps to it (the `0x1ef` manifest `{0x2000a000, 0x08012fc5, …}` is documented above; the reset-word disassembles to a mid-function tail because it is reached via the bootloader's hand-off context, not as first instruction).
