# MFB Tanzmaus — Firmware Update Protocol

Reverse-engineered from the four [MFB OS update files](../mfb/firmware/)

| Version | Data frames¹ | Final frame² | Header addr | Image bytes |
|---|---|---|---|---|
| 1.6 | 3382 | 48 B @ addr 3383 | 0x0D38 (3384) | 111,638 |
| 1.61 | 3391 | 38 B @ addr 3392 | 0x0D41 (3393) | 111,926 |
| 1.62 | 3414 | 29 B @ addr 3415 | 0x0D58 (3416) | 112,677 |
| 1.63 | 3416 | 29 B @ addr 3417 | 0x0D5A (3418) | 112,743 |

¹ full 52-byte data frames, addr 1..N-2
² the last data frame (addr N-1) is shorter — the image is not 33-byte aligned; it carries the image tail and has no checksum field. The header frame sits at addr N.

Analysis [python scripts](firmware-scripts/)
 
| File | Contents |
|---|---|
| `fw_cksum.py` | Embeds the 21-bit XOR-linear checksum weight tables and verifies every frame across all four firmware versions. |
| `fw_decoder.py` | Unpacks 7-bit MIDI-safe payload bytes back to 8-bit and reconstructs the firmware image. Verifies address contiguity and every 3-byte checksum. |
| `fw_disasm.py` | Disassembles the decoded image to confirm the Cortex-M (Thumb-2) code. |
| `fw_dispatcher.py` | Heuristic SysEx analysis: single-pass decode, vector-table scan, peripheral-constant reconstruction, USART-shaped access map, command-immediate inventory. See the [SysEx reply-probe runbook](sysex-probes.md). |
| `fw_trailer.py` | Decodes the final (short) frame = the image tail: unpacks and disassembles it, lists embedded SRAM/flash words, and reports image-level checksums (global-signature checks returned negative). |
| `fw_ramxref.py` | Raw byte-occurrence scan (decode-noise immune) plus `movw`/`movt`-adjacency and literal-pool inventory for the SRAM / peripheral addresses the app references. |

---

## Delivery

A `.syx` is one sequential SysEx session of **N cmd-01 frames with contiguous
addresses 1..N**:
- addr **1..N-2**: full **52-byte data frames**,
- addr **N-1**: the **final (short) data frame** — the image tail, 29–48 bytes, no checksum field,
- addr **N**: the **metadata header** frame (52 bytes), its address equals the total frame count N.

Every frame shares the shell `F0 00 21 0B 04 00 01`, the MFB SysEx header, device ID `0x0B`, and command byte `0x01` (firmware upload).

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
| 8–9 | address | big-endian, both bytes 7-bit: `addrHi<<7 \| addrLo`, contiguous 1..N |
| 10–47 | payload | 38 bytes of 7-bit-safe firmware data |
| 48–50 | checksum | 21-bit XOR-linear code (see Checksums) |

### Metadata header frame

The **first** frame carries version/signature metadata. Its address equals **the total frame count** (a length/count sentinel), i.e. two past the last data-frame address.

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

The **final data frame** (addr `N-1`) is shorter than 52 bytes because the image
is not a multiple of 33 bytes: it is the last chunk of the firmware itself, sent
in a partial frame (no checksum field). Unpacked with the same LSB-first 7→8
rule, it yields the end of the flash image — a small Thumb-2 routine
(`70 47` = `bx lr`) followed by 4-byte-aligned RAM words that are stable across
all four versions:

| Version | Frame len | Unpacked tail (bytes) |
|---|---|---|
| 1.6 | 48 | `11 12` + `str r2,[r3,#4] · ldr r0,[r3,#4] · ldr r1,[r3] · adds r2,r0,#1 · eor r0,r2,r1,lsr#8 · str r0,[r3,#4] · bx lr` + `65 01 00 20` `bc 00 00 20` `80 40 37 10` |
| 1.61 | 38 | `adds r2,r0,#1 · eor r0,r2,r1,lsr#8 · str r0,[r3,#4] · bx lr` + `65 01 00 20` `bc 00 00 20` `02 5f 00` |
| 1.62 | 29 | `bx lr` + `61 01 00 20` `bc 00 00 20` `00 f8 80` |
| 1.63 | 29 | `bx lr` + `61 01 00 20` `bc 00 00 20` `00 f0 81` |

The words (LE, so `65 01 00 20` = `0x20000165`) are **`0x20000165`** (V1.6/1.61)
or **`0x20000161`** (V1.62/1.63) plus **`0x200000bc`** in every version. They are
4-byte aligned, sit at the very end of the image, and raw byte-occurrence scans
show the app code never references them (each appears exactly once per image) —
they are a small **metadata/boot footer**, most likely consumed by the update
mechanism rather than the app. Note the app *does* reference nearby low-SRAM
addresses heavily: V1.62/1.63 build/use `0x20000164` (16 occurrences) and
`0x200000cc` (13), V1.6/1.61 use different low-SRAM words (`0x200000da`,
`0x2000013e`, …), i.e. the app's RAM layout shifts between versions.

Image-level checksums (CRC32 / CRC-16-CRC_HQX / XOR8 / SUM8 over the image body)
do **not** match any tail word: the tail is not a global image signature.

---

## Reconstructing the image

The 38 payload bytes are **not** raw data — they are MIDI-safe (7-bit) and must be re-packed to 8-bit, **LSB-first**, **per frame** (reset the accumulator each frame), then concatenated **in address order**, excluding only the metadata header frame (addr N). The final short frame (addr N-1) is part of the image. Image base is `0x08000000` (STM32F303 flash origin).

```
per frame: acc |= (byte & 0x7f) << nb; nb += 7; emit a byte when nb >= 8
```

Image sizes are listed above (all < 256 KB flash). Addressing starts with an all-zero leading region (see "Image layout"). Verified: the final frame, unpacked alone, yields genuine Cortex-M Thumb-2 code (`70 47` = `bx lr`), proving the transform is correct.

---

## Hardware

The MCU is an **STM32F303CCT6** (Cortex-M4F, 256 KB flash, 40 KB SRAM). The initial stack-pointer sentinel `0x2000a000` equals exactly `0x20000000 + 40 KB` (SRAM top), confirming the decode and the memory map.

## Image layout

`fw_dispatcher.py` reads a vector table at image offset **`0x1ef`** with a compact set of entries (**claimed — see the Known issue below**):

| Index | Word | Meaning |
|---|---|---|
| 0 | `0x2000a000` | Initial SP = SRAM top |
| 1 | reset vector | grows per version |
| 2–6 | shared handler / faults | |
| 7–10 | `0` | reserved, not populated |

The reset handler disassembles to coherent Cortex-M init code (nibble `cmp #0xf` parameter-zeroing loops, `pop {r3, pc}` epilogues). The image has a short **0x62-byte** leading zero prefix (frames 1..~3 carry all-zero payloads) before genuine code; `0x2000a000` appears exactly once in the image (a genuine constant, the SRAM-top sentinel).

#### Known issue (fw_dispatcher.py — review pending)

`0x1ef` is **not 4-aligned**, but the Cortex-M exception table must be
word-aligned for hardware fetch. The actual leading zero run is **0x62 bytes**,
not 0x1ef; the claimed reset vector (`0x08012fc4`) decodes to a mid-function
tail (`pop {r4,r5,pc}`), not init; and no 4-aligned SP-word + function-pointer
cluster exists anywhere in the image. These bytes look like a coincidence of
data rather than a real vector table. The true entry point / vector arrangement
is unresolved.

---

## Checksums

Two fields cover the frame.

### 3-byte checksum (bytes 48–50) — RECOVERED

A **21-bit XOR-linear (GF(2)) code** over the 16-bit frame **address** and **all 38 payload bytes** (including col36/37). Verified **0 mismatches over 13,607 frames** (all data frames plus the four metadata header frames, whose checksum is computed on the 38 payload bytes the same way).

- Same (address, payload) ⇒ same checksum — 0 conflicts over 10,675 keys.
- The middle byte is always `0x00`/`0x01` — it carries the high bit of the 21-bit
  word; bytes 0 and 2 carry the bulk.
- Not a standard CRC-16/CRC-8 (common polynomials brute-forced, no match) — a
  proprietary linear code.
- Payload bytes contribute only their 7 low bits (bit 7 = 0); address uses bits 0–15.
- Per-bit 21-bit weight tables are embedded in `reverse/firmware-scripts/fw_cksum.py`
  (`ADDR_BITS`, `PAYLOAD`).

For all-zero data the checksum depends only on the address, e.g. `addr 0x0001 → 4d 00 78`, `0x0002 → 57 01 48`, `0x0004 → 62 01 28`, `0x0007 → 78 00 18`.

```
value = XOR_{addr bit b set}  ADDR_BITS[b]
      ^ XOR_{byte k, bit b set} PAYLOAD[k][b]      k=0..37, b=0..6

checksum bytes:  ck[i] = (value >> 7*i) & 0x7F
```

This is one of the two values needed to originate valid firmware frames.

### Columns 36 & 37 — deterministic, algorithm TBD

Columns 36–37 are a **5-bit field** (`col36 | col37<<4`; col36 is 4 bits, col37 is 1 bit) that is a deterministic, **non-linear** function of `(address, payload[0:36])`:

- 0 conflicts over 6,645 distinct `(addr, data)` keys; depends on the address.
- Not the sample-protocol CRC, not common CRC-5/8/16, not modular-sum/Fletcher, not byte-xor/fold, not packing leftovers, and **not XOR-linear** in any framing (address as 16 bits, 7 bits, or single byte) — so a substitution/table-based or clocked-LFSR checksum is suspected.

This is the **one remaining layout unknown** and only matters for *originating* frames (the 3-byte checksum — which the device also validates — is solved).

---

## Update bootloader

The app image contains **no flash-programming code**: no F303 FLASH unlock keys (`0x45670123`/`0xcdef89ab`), no writes to `FLASH->CR`/`KEYR`, no SysEx OS-receive path. Startup only does standard init (SCB->AIRCR priority group, RCC clock enables).

The OS-update receive/validate/flash logic therefore lives in a **separate bootloader not shipped in the `.syx`**; the file carries only the application image (whose last 4-byte-aligned words — the `0x20000161`/`0x20000165` + `0x200000bc` footer — are plausibly the hand-off data the bootloader reads). Because of this, the update code (which computes/checks the fields above) is not recoverable from the shipped artifacts alone.

---

## Device ID

`0x0B` is constant across every official firmware image: the device ID is hardcoded and two chained Tanzmauses cannot be addressed individually.

## Empirical probes

Whether the Tanzmaus ever **transmits** SysEx in response to a received message
(identity / handshake / reply) is answered empirically in the
[SysEx reply-probe runbook](sysex-probes.md). Short answer: **fire-and-forget** —
the firmware never replies.

Static context (V1_63, via `fw_dispatcher.py`): the image disassembles fully
(49,832 Thumb-2 instructions) with genuine code from near the image start; it
uses movw/movt + offset addressing with **no 32-bit peripheral literal pools**
for RCC/USART/GPIO, and carries USART-shaped accesses (`[rN,#0x28]`/`[rN,#0x24]`
= TDR/RDR-style) clustered at `0x080003B6..0x0800234A`. A true `cmp #0xF0`
(SysEx `F0`) site exists. The main remaining unknowns — exact MIDI USART
identity and the full RX command set — are best answered empirically.

---

## Remaining unknowns

- Exact col36/col37 algorithm (above).
- Meaning of the header signature fields and of the final-frame footer words
  (`0x20000161`/`0x20000165` + `0x200000bc`), and of the low-SRAM addresses the
  app itself builds/reads (`0x20000164`, `0x200000cc` in V1.62/1.63).
- The exact MIDI USART identity (the app uses an unusual constant-construction
  pattern that evades literal-pool / `movw`/`movt` adjacency analysis; the
  USART-shaped accesses cluster at `0x080003B6..0x0800234A` but the peripheral
  base address could not be statically resolved).
- Whether the bootloader flashes the whole 256 KB or only the app region (needs
  on-device/bootloader access).
- The true vector table / entry point — the documented `0x1ef` offset is
  ARM-illegal (not 4-aligned) and the claimed reset vector decodes to a
  mid-function tail, not init code.
