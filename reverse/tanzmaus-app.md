# MFB Tanzmaus — MIDI SysEx Protocol

Reverse-engineered from `MFB Tanzmaus Sample Manager v1.0.12` ([linuxbender/tanzmaus-app](https://github.com/linuxbender/tanzmaus-app)).

## Overview

| Aspect | Detail |
|---|---|
| Direction | App → Tanzmaus (one-way, fire-and-forget) |
| Transport | Web MIDI API with SysEx enabled |
| Message pacing | 22 ms between every message |
| Protocol | Proprietary MFB SysEx over standard MIDI |

---

## SysEx Header

Every message shares a common 5-byte header:

```
00 21 0B 04 00
│  │   │  │  └─ 0x00  sub-command / message variant (always 0 in header)
│  │   │  └──── 0x04  message class: sample transfer
│  │   └─────── 0x0B  device ID: Tanzmaus (decimal 11)
│  └──────────── 0x21  manufacturer ID: MFB (decimal 33)
└──────────────── 0x00  universal non-realtime / padding
```

Wrapped with `F0` (SysEx start) and `F7` (SysEx end) by the app:

```
F0 00 21 0B 04 00 <cmd> [payload...] F7
```

---

## Commands

| Cmd | Hex | Purpose | Builder |
|---|---|---|---|
| **6** | `0x06` | Select target slot | `hm(slotNo)` |
| **5** | `0x05` | Sample data page | `Sm(samples, pageAddr)` |
| **7** | `0x07` | End of upload | `gm()` |

---

## Upload Sequence

For each slot upload:

```
select slot  →  N data pages (11 frames each)  →  end of upload
```

Frame formats and timing below.

---

## Message Formats

### Slot Select

- `hm = m => bf([...Sf, 6, m])` — command `0x06`, one argument: slot number 0–15
- Bank is NOT in this message; bank is implied by page addresses (see Page Address Map)

### End of Upload

- `gm = () => bf([...Sf, 7])` — command `0x07`, empty payload

### Sample Data Page (60 bytes × 11 sub-frames per page)

```
F0  00 21 0B 04 00 05  addrLo  addrHi  subIdx  [48 data bytes]  chk  F7
```

| Byte | Content |
|---|---|
| 0 | `0xF0` — SysEx start |
| 1–5 | Header: `00 21 0B 04 00` |
| 6 | Command: `0x05` (sample data) |
| 7 | Page address, low 7 bits |
| 8 | Page address, high 7 bits (together: 14-bit address) |
| 9 | Sub-frame index: 0–10 |
| 10–57 | 48 data bytes: 24 samples × (low7, high7) pairs |
| 58 | Checksum: 7-bit CRC variant |
| 59 | `0xF7` — SysEx end |

Each sub-frame carries **24 samples** encoded as 14-bit words split into 7+7-bit pairs:

```
[sample0_low, sample0_high, sample1_low, sample1_high, ...]
```

Each page carries **264 samples** total (11 sub-frames × 24 samples).

---

## Checksum Algorithm

Computed over the 57-byte core payload (bytes 0–56: header + command + address + subIdx + data), seeded at 0, masked to 7 bits:

```javascript
dm = (m, E) => {
  E ^= m << 1 & 255;
  E & 128 && (E ^= 9);
  return (E ^ m & 120 ^ m << 4 & 255 ^ m >> 3 & 15) & 127;
};
```

- `m` = accumulated checksum state
- `E` = current byte
- Result is 7 bits (0–127), MIDI-data-safe

---

## Page Address Map

Bank and slot determine the starting page address. The bank is **encoded in the address**, not in the slot-select command.

```javascript
rm = (bank, slot) =>
  slot < 4  ? (bank * 4 + slot) * 91
  : slot < 12 ? 728 + (bank * 8 + (slot - 4)) * 182
  :             3640 + (bank * 4 + (slot - 12)) * 364;
```

| Bank | Slot | Page Start Address |
|---|---|---|
| 0 | 0 | 0 |
| 0 | 1 | 91 |
| 0 | 2 | 182 |
| 0 | 3 | 273 |
| 0 | 4 | 728 |
| 0 | 5 | 910 |
| ... | ... | ... |
| 0 | 12 | 3640 |
| 0 | 13 | 4004 |
| 0 | 14 | 4368 |
| 0 | 15 | 4732 |
| 1 | 0 | 364 |
| 1 | 1 | 455 |
| ... | ... | ... |

During upload, the address sent to the device = `pageStartAddr + pageIndex`.

---

## Slot Capacity (by position within bank)

| Slot (within bank) | Max Samples | Duration @ 44.1 kHz |
|---|---|---|
| 1–4 | 22,000 | 0.5 s |
| 5–12 | 44,000 | 1.0 s |
| 13–16 | 88,000 | 2.0 s |

---

## Audio → Sample Conversion

Before upload, audio files are processed:

1. Decode at **44.1 kHz** via `AudioContext.decodeAudioData`
2. Truncate to slot capacity (`Ln`)
3. Average all channels to mono
   - Differs from the official MFB tool, which takes channel 0 only (no averaging)
4. Convert float samples → 12-bit unsigned:

```javascript
sample = (Math.trunc(floatSample * 32768) + 32768 & 0xFFFF) >> 4;
// Result: 0–4095 (12-bit), stored in Uint16
```

5. Pad array to multiple of 264 (page size boundary)

---

## Upload Scheduler

```javascript
bm = (audioData, slotInfo) => {
  const script = [];
  let timeCursor = 0;  // in 1/48000 s units

  // 1. Select slot
  script.push({ data: hm(slotInfo.slotNo), offsetMs: timeCursor / 48000 * 1000 });
  timeCursor += 1056;

  // 2. Send data pages (264 samples each)
  for (let i = 0; i < sampleCount; i += 264) {
    const pageIndex = i / 264;
    const pageData = new Uint16Array(264);
    pageData.set(audioData.subarray(i, i + 264));

    for (const frame of Sm(pageData, slotInfo.pageStartAddr + pageIndex)) {
      script.push({ data: frame, offsetMs: timeCursor / 48000 * 1000 });
      timeCursor += 1056;
    }
  }

  // 3. End of upload
  script.push({ data: gm(), offsetMs: timeCursor / 48000 * 1000 });
  timeCursor += 1056;

  return script;
};
```

All messages are pre-scheduled with `performance.now()` timestamps:

```javascript
const start = performance.now();
for (const { data, offsetMs } of script) {
  device.output.send(data, start + offsetMs);
}
```

Total upload time = `lastOffsetMs + 500 ms` (safety tail).

---

## Connection Handling

```javascript
// Request SysEx access
const midiAccess = await navigator.requestMIDIAccess({ sysex: true });

// Enumerate outputs
midiAccess.outputs.forEach(output => { /* list devices */ });

// Auto-refresh on plug/unplug
midiAccess.onstatechange = () => { /* re-enumerate */ };
```

No `onmidimessage` / MIDIInput handler exists — the protocol is strictly one-way.

---

## State Machine

| Status | Meaning |
|---|---|
| `ready` | MIDI access granted, devices available |
| `unsupported` | Browser doesn't support Web MIDI API |
| `permission-denied` | User denied SysEx access |
| `uploading` | Transfer in progress (0–100% progress) |
| `done` | Upload complete |

---

## Example: Uploading 44,000 samples to Bank 1, Slot 5

1. Slot select: `F0 00 21 0B 04 00 06 04 F7`
2. Pages: ⌈44000 / 264⌉ = 167 pages × 11 frames = **1,837 data frames**
3. End: `F0 00 21 0B 04 00 07 F7`
4. Total messages: 1,839
5. Transfer time: 1,839 × 22 ms + 500 ms ≈ **41.0 seconds**
