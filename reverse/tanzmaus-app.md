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
4. Convert float samples → 12-bit unsigned (see [sysex.md](../sysex.md#sample-data-encoding)).
5. Pad to multiple of 264

### Factory default JSON (
  
  
All the 32 [factory samples](factory-samples.md) sounds are embeded in a json file : [tanzmaus-default.json](https://github.com/linuxbender/tanzmaus-app/blob/gh-pages/tanzmaus-default.json)

- 32 assignments, each with `slotIndex`, `fileName`, `audioData` (base64), `uploadStatus`
- `audioData` is raw 12-bit unsigned PCM in 16-bit LE words (no WAV header)
- Rate: 44.1 kHz, resampled from the original 48 kHz factory default before embedding
- "Restore to factory" uploads these 44.1 kHz samples

#### Slot capacities

| Slots | Official tool | Tanzmaus app JSON |
|---|---|---|
| sp1 1–8, sp2 1–4 | 22,000 | 22,176 |
| sp1 9–16, sp2 5–12 | 44,000 | 44,088 / 44,352 |
| sp2 13–16 | 88,000 | 88,176 |

- Values are padded by ~176 samples beyond the tool's limits
- sp1 slots 13–16 have 264 more samples than sp2 slots 5–12 (44,352 vs 44,088)

#### Conflict

The sample length from the JSON data conflict with the app's capacity logic:

JSON data shows sp1/13–16 are 1s, but the interface labels them as 2s. The `yf()` function uses `index % 16`, ignoring bank-specific differences.

**JSON data (asymmetric)**

- sp1 13–16: 44,352 samples (1s capacity)
- sp2 13–16: 88,176 samples (2s capacity)

**`yf()` function (symmetric)**

```javascript
function yf(m) {
  const E = m % 16;
  return E < 4 ? "0.5s" : E < 12 ? "1s" : "2s"
}
```

**Interface labels (symmetric)**

Labels for slots 13–16 = "2s" for both sp1 and sp2.

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

Page start addresses are computed from bank + slot as described in [sysex.md](../sysex.md#address-map) (e.g. bank 0: slot 0 = 0, slot 4 = 728, slot 12 = 3640; bank 1: slot 0 = 364).

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
