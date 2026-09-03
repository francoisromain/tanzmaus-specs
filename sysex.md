# MFB Tanzmaus — Sample Upload SysEx Protocol

From the official MFB sample tool app [source code](mfb/tool/TanzmausSampleTool/). 

Use this to build an app that uploads samples to the Tanzmaus.

## Header

Every message is wrapped in SysEx with a hardcoded header and device ID:

```
F0  00 21 0B 04 00  <cmd>  [payload]  F7
│   └───┬────┘                      │
F0   MFB device ID 0x0B            F7
     (00 21 0B 04 00)
```

- Device ID `0x0B` (decimal 11) is **hardcoded** — not user-selectable, no MIDI channel.
- No reply/ack; the protocol is one-way, fire-and-forget.

## Commands

| Cmd | Purpose |
|---|---|
| `0x05` | Sample data page |
| `0x06` | Select target slot |
| `0x07` | End of upload |

## Upload sequence

```
select slot  →  N data pages (11 frames each)  →  end of upload
```

Send messages with **22 ms** between them.

## Message formats

### Slot select — `0x06`

```
F0  00 21 0B 04 00  06  <slot 0-15>  F7
```

`slot` = 0–15. The bank is NOT in this message — it is implied by the page addresses (see Address map).

### Sample data page — `0x05`

```
F0  00 21 0B 04 00  05  addrLo  addrHi  subIdx  [48 data bytes]  chk  F7
```

| Byte | Content |
|---|---|
| 7 | `addrLo` — page address, low 7 bits |
| 8 | `addrHi` — page address, high 7 bits (together: 14-bit address) |
| 9 | `subIdx` — sub-frame index 0..10 |
| 10–57 | 48 data bytes = 24 samples × (low7, high7) |
| 58 | `chk` — checksum, 7 bits |

- 11 sub-frames per page × 24 samples = **264 samples per page**.
- Each sample is a 14-bit word split into 7+7-bit pairs: `[s0_lo, s0_hi, s1_lo, s1_hi, ...]`.
- Address sent per frame = `pageStartAddr + pageIndex` (pageIndex = 0, 1, 2, ...).

### End of upload — `0x07`

```
F0  00 21 0B 04 00  07  F7
```

## Checksum

Single 7-bit CRC over the 57-byte core payload (bytes 0–56: header + cmd + addr + subIdx + data), seeded at 0, masked to 7 bits. From `crc7.cpp`:

```c
unsigned char CalcCrc(unsigned char crc, unsigned char data) {
    data ^= crc << 1;
    if (data & 0x80)
        data ^= 9;
    crc = data ^ (crc & 0x78) ^ (crc << 4) ^ ((crc >> 3) & 15);
    return crc & 0x7f;
}
```

- In the wire format (`F0 ... F7`), the CRC covers the 57 bytes **after** F0 and **before** the checksum byte: `00 21 0B 04 00 05 addrLo addrHi subIdx [48 data bytes]`. F0 and F7 are excluded from the CRC computation.
- Init `crc = 0`, feed each byte, result is 0–127 (MIDI-data-safe).

## Address map

Bank (`sampleDest`) and slot (`sampleNo`, 0-based) map to a starting page address. The bank is encoded in the address, not in slot-select.

```
pageStartAddr =
  sampleNo < 4    ? (sampleDest * 4 + sampleNo) * 91
  : sampleNo < 12 ? 728 + (sampleDest * 8 + (sampleNo - 4)) * 182
  :                  3640 + (sampleDest * 4 + (sampleNo - 12)) * 364
```

Example page starts (bank 0): slot 0 = 0, slot 1 = 91, slot 4 = 728, slot 12 = 3640.

## Sample data encoding

1. Decode audio file (.wav/.aif). Sample sizes are based on **44.1 kHz**; MIDI transfer runs at **48 kHz**.
2. Truncate to the slot's capacity (see below).
3. Take channel 0 (no averaging).
4. Convert float samples → 12-bit unsigned (0–4095): `(uint16_t)(sample * 32768.0 + 32768.0) >> 4`
5. Pad to a multiple of 264.

## Slot lengths

| Slot (within bank) | Max samples | Duration @ 44.1 kHz |
|---|---|---|
| 1–4 | 22,000 | 0.5 s |
| 5–12 | 44,000 | 1.0 s |
| 13–16 | 88,000 | 2.0 s |

- Files longer than the target slot are **truncated**.
- Recommended: samples should start at a zero crossing to avoid clicks.
- Overwriting an existing sample replaces it.
