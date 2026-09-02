# MFB Tanzmaus Sample Tool — Source Walkthrough

- [Source files](../mfb/tool/TanzmausSampleTool/)
- Author: Sebastian Preller, Jan 2017
- Framework: JUCE (C++)

## Source Files

| File | Role |
|---|---|
| `Source/Main.cpp` | JUCE app entry, window setup |
| `Source/TanzmausSampleTool.cpp/.h` | UI layout, audio read, upload orchestration |
| `Source/crc7.cpp/.h` | SysEx message builder + CRC7 checksum |
| `Source/DragAndDropButton.cpp/.h` | Drag-and-drop file input (`.wav`, `.aif`) |
| `Source/pBar.cpp/.h` | Progress bar widget |

## Hardware Requirements

- Firmware ≥ 1.6
- MIDI input connected to interface output
- Sequencer stopped, device in **Play/Mute mode** (REC LED off)

## Usage

1. Select MIDI port in the app
2. Select bank (0 or 1) and slot (0–15)
3. Drag & drop `.wav` or `.aif` onto the button
4. Press **Start Transmission**
5. Overwrites existing samples at same bank/slot

### Tips

- Start samples at a **zero crossing** to avoid clicks
- Files longer than the bank duration are truncated

## MIDI SysEx Protocol

Device ID: `0x0B` (Tanzmaus)
Header (all messages): `00 21 0B 04`

### Slot Select — cmd `0x06`

```
F0 00 21 0B 04 00 06 <slot 0-15> F7
```

### Page Data — cmd `0x05`

```
F0 00 21 0B 04 00 05 <addrLo7> <addrHi7> <subIdx 0-10> [48 data bytes] <crc7> F7
```

- `addrLo7`: `pageAddr & 0x7F`
- `addrHi7`: `(pageAddr >> 7) & 0x7F`
- Payload: 58 bytes (before F0/F7 wrapping)

### End Upload — cmd `0x07`

```
F0 00 21 0B 04 00 07 F7
```

## CRC7 Checksum

From `crc7.cpp:21-30`. Computed over bytes 0–56 of each page message (header + addr + subIdx + 48 data bytes). Stored at byte 57.

```c
unsigned char CalcCrc(unsigned char crc, unsigned char data) {
    data ^= crc << 1;
    if (data & 0x80)
        data ^= 9;
    crc = data ^ (crc & 0x78) ^ (crc << 4) ^ ((crc >> 3) & 15);
    return crc & 0x7f;
}
```

- Init: `crc = 0`
- Feed each of the 57 bytes through `CalcCrc`
- Final byte = `crc & 0x7F`

## Sample Memory Layout

2 banks, 16 slots each (0–15 per bank).

### Sample Sizes

| Sample # | Samples | Duration | Pages |
|---|---|---|---|
| 1–4 | 22,000 | 0.5s | 84 |
| 5–12 | 44,000 | 1s | 167 |
| 13–16 | 88,000 | 2s | 334 |

### Page Start Address Formulas

`sampleDest`: bank (0 or 1)
`sampleNo`: slot (0–15 within bank)

| Samples | Formula |
|---|---|
| 1–4 (0.5s) | `((sampleDest × 4) + sampleNo) × 91` |
| 5–12 (1s) | `728 + ((sampleDest × 8) + (sampleNo − 4)) × 182` |
| 13–16 (2s) | `3640 + ((sampleDest × 4) + (sampleNo − 12)) × 364` |

### Page Structure

- 264 samples per page (24 samples × 11 sub-frames)
- Each sub-frame → 1 SysEx message (48 data bytes)

## Data Packing (per sub-frame)

24 samples × 14-bit unsigned each → 48 bytes:

```
byte[0]  = sample[0] & 0x7F         // low 7 bits
byte[1]  = (sample[0] >> 7) & 0x7F  // high 7 bits
byte[2]  = sample[1] & 0x7F
byte[3]  = (sample[1] >> 7) & 0x7F
...
byte[47] = (sample[23] >> 7) & 0x7F
```

## Audio Conversion

From `TanzmausSampleTool.cpp:208`.

- Input: `.wav` or `.aif` via JUCE `AudioFormatManager`
- Float sample `[-1.0, 1.0]` → 12-bit unsigned:

```c
uint16_t raw = (uint16_t)(sample * 32768.0 + 32768.0) >> 4;
```

- File shorter than `sampleSize` → zero-padded
- File longer → truncated

## Transfer Timing

- 1056 samples between SysEx messages (22ms @48kHz)
- Source comment says `//ca.20ms` — misleading, actual value is 22ms
- Sent in batch via `MidiOutput::sendBlockOfMessages` at 48kHz rate

## Upload Sequence

1. `AddStartMessage(sampleNo)` → select bank
2. For each page (264 samples): `AddPage(data, pageAddr)` → 11 SysEx messages
3. `AddStopMessage()` → end transfer


