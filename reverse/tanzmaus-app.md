# MFB Tanzmaus Sample Manager — Web App Walkthrough

Reverse-engineered from `MFB Tanzmaus Sample Manager v1.0.12` ([linuxbender/tanzmaus-app](https://github.com/linuxbender/tanzmaus-app)).

## Overview

| Aspect | Detail |
|---|---|
| Direction | App → Tanzmaus (one-way, fire-and-forget) |
| Transport | Web MIDI API with SysEx enabled |
| Message pacing | 22 ms between every message |
| Protocol | Proprietary MFB SysEx over standard MIDI — see [sysex.md](../sysex.md) |

## Protocol

See [sysex.md](../sysex.md) for the full SysEx spec (header, commands, CRC7, address map, data encoding, slot lengths).

## Audio → Sample Conversion

1. Decode at **44.1 kHz** via `AudioContext.decodeAudioData`
2. Truncate to slot capacity
3. **Average all channels to mono**
   - Differs from the official MFB tool, which takes channel 0 only (no averaging)
4. Convert float samples → 12-bit unsigned (see [sysex.md](../sysex.md#sample-data-encoding)):
5. Pad to multiple of 264

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

## State Machine

| Status | Meaning |
|---|---|
| `ready` | MIDI access granted, devices available |
| `unsupported` | Browser doesn't support Web MIDI API |
| `permission-denied` | User denied SysEx access |
| `uploading` | Transfer in progress (0–100% progress) |
| `done` | Upload complete |

## Page Address Table

Full mapping from [sysex.md](../sysex.md#address-map):

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

## Worked Example: Bank 1, Slot 5 (44,000 samples)

1. Slot select: `F0 00 21 0B 04 00 06 04 F7`
2. Pages: ⌈44000 / 264⌉ = 167 pages × 11 frames = **1,837 data frames**
3. End: `F0 00 21 0B 04 00 07 F7`
4. Total messages: 1,839
5. Transfer time: 1,839 × 22 ms + 500 ms ≈ **41.0 seconds**

## JavaScript Function Reference

These are the minified function names from the source — useful for reading the bundled app:

| Function | Purpose |
|---|---|
| `hm(slotNo)` | Build slot select message (cmd `0x06`) |
| `Sm(samples, pageAddr)` | Build 11 data page messages (cmd `0x05`) |
| `gm()` | Build end-of-upload message (cmd `0x07`) |
| `bf(bytes)` | Wrap byte array with F0/F7 SysEx framing |
| `dm(crc, byte)` | CRC7 accumulator (same algorithm as [sysex.md](../sysex.md#checksum)) |
| `rm(bank, slot)` | Compute page start address from bank + slot |
| `bm(audioData, slotInfo)` | Build complete upload schedule |
