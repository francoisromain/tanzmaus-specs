# MFB Tanzmaus — Firmware Update Protocol

Reverse-engineered from the four [MFB OS update files](../mfb/firmware/)

| Version | Data frames | Image bytes |
|---|---|---|
| 1.6 | 3383 | 111,639 |
| 1.61 | 3392 | 111,936 |
| 1.62 | 3415 | 112,695 |
| 1.63 | 3417 | 112,761 |

Analysis [python scripts](firmware-scripts/)
 
| File | Contents |
|---|---|
| `fw_cksum.py` | Embeds the 21-bit XOR-linear checksum weight tables and verifies every frame across all four firmware versions. |
| `fw_decoder.py` | Unpacks 7-bit MIDI-safe payload bytes back to 8-bit and reconstructs the firmware image. |
| `fw_disasm.py` | Disassembles the decoded image to confirm the Cortex-M (Thumb-2) code. |

---

## Delivery

A `.syx` is one sequential SysEx session: 
- a **metadata header**, 
- then **N data frames** (addr 1..N), 
- then a **trailer**. 

Every frame shares the shell `F0 00 21 0B 04 00 01`, the MFB SysEx header, device ID `0x0B`, and command byte `0x01` (firmware upload).

| Segment | Length | Count |
|---|---|---|
| Metadata header | 52 bytes | 1 |
| Data frames | 52 bytes | N |
| Trailer | 29–48 bytes (varies per version) | 1 |

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

The **first** frame carries version/signature metadata. Its address equals **the total frame count** (a length/count sentinel), i.e. one past the data-frame address range.

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
- address `0x1A41` = `(0x1A<<7)|0x41` = 3393 = 3391 data + trailer + header
- `data[0:16]` = `00 00 3c 60 0b 20 00 53 14 00 00 00 00 00 00 ...` signature
- data tail `00 01` = end marker; checksum = `1f 01 2a`

### Trailer frame

The **final** frame is shorter than 52 bytes (29–48) and closes the session. Its address sits at `total_frames - 1` (one less than the header's), consistent with a closing marker:

| Version | Trailer length | Bytes after `F0 00 21 0B 04 00 01 00` |
|---|---|---|
| 1.6 | 48 | `1a 37 11 24 68 02 06 0b 5a 0c ... 5d 01 41 F7` |
| 1.61 | 38 | `1a 40 42 38 08 54 1e 02 08 2c ... 5f 00 24 F7` |
| 1.62 | 29 | `1a 57 70 0e 01 78 1b 2c 00 ... 7c 00 75 F7` |
| 1.63 | 29 | `1a 59 70 0e 01 78 1b 2c 00 ... 78 01 7b F7` |

Unpacked, the trailer yields per-version **RAM pointers** (`0x20000161`/`0x20000165`, `0x200000bc`); the exact payload meaning (global image checksum / verify command / done marker) is undetermined.

---

## Reconstructing the image

The 38 payload bytes are **not** raw data — they are MIDI-safe (7-bit) and must be re-packed to 8-bit, **LSB-first**, **per frame** (reset the accumulator each frame), then concatenated **in address order**, excluding the metadata header and trailer. Image base is `0x08000000` (STM32F303 flash origin).

```
per frame: acc |= (byte & 0x7f) << nb; nb += 7; emit a byte when nb >= 8
```

Image sizes are listed above (all < 256 KB flash). Addressing starts with an all-zero leading region (see "Image layout"). Verified: the trailer, unpacked alone, yields genuine Cortex-M Thumb-2 code (`70 47` = `bx lr`), proving the transform is correct.

---

## Hardware

The MCU is an **STM32F303CCT6** (Cortex-M4F, 256 KB flash, 40 KB SRAM). The initial stack-pointer sentinel `0x2000a000` equals exactly `0x20000000 + 40 KB` (SRAM top), confirming the decode and the memory map.

## Image layout

The vector table sits at image offset **`0x1ef`** with a compact set of entries:

| Index | Word | Meaning |
|---|---|---|
| 0 | `0x2000a000` | Initial SP = SRAM top |
| 1 | reset vector | grows per version |
| 2–6 | shared handler / faults | |
| 7–10 | `0` | reserved, not populated |

The reset handler disassembles to coherent Cortex-M init code (nibble `cmp #0xf` parameter-zeroing loops, `pop {r3, pc}` epilogues). The image flashes at base `0x08000000` with **no VTOR rebase** needed; its ~0x1ef-byte leading zero prefix (equivalently, frames 1..~27 carry all-zero payloads) is reserved descriptor/boot space.

---

## Checksums

Two fields cover the frame.

### 3-byte checksum (bytes 48–50) — RECOVERED

A **21-bit XOR-linear (GF(2)) code** over the 16-bit frame **address** and **all 38 payload bytes** (including col36/37). Verified **0 mismatches over 13,604 data frames** across all four versions.

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

The OS-update receive/validate/flash logic therefore lives in a **separate bootloader not shipped in the `.syx`**; the file carries only the application image. Because of this, the update code (which computes/checks the fields above) is not recoverable from the shipped artifacts alone.

---

## Device ID

`0x0B` is constant across every official firmware image: the device ID is hardcoded, has **no user-configurable selection step** in the OS-update procedure, and two chained Tanzmauses cannot be addressed individually.

---

## Remaining unknowns

- Exact col36/col37 algorithm (above).
- Meaning of the header signature fields, trailer payload, and full exception vector
  metadata (SysTick/PendSV/SVCall) — low-risk, not needed to parse files.
- Whether the bootloader flashes the whole 256 KB or only the app region (needs
  on-device/bootloader access).
