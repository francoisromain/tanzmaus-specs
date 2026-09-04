# MFB Tanzmaus Sample Tool, Source Walkthrough

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

## Usage

In the app:

1. Select MIDI port 
2. Select bank (0 or 1) and slot (0–15)
3. Drag & drop `.wav` or `.aif` onto the button
4. Press `Start Transmission`
5. Overwrites existing samples at same bank/slot

## Protocol

See [sysex.md](../sysex.md) for the full SysEx protocol spec (header, commands, CRC7, address map, data encoding, slot lengths).

## Implementation Notes

### Transfer Timing

- 1056 samples between SysEx messages (22ms @48kHz transfer rate, distinct from the machine's 44.1 kHz playback rate, see [sysex.md](../sysex.md))
- Source comment says `//ca.20ms`, misleading, actual value is 22ms
- Sent in batch via `MidiOutput::sendBlockOfMessages` at 48kHz transfer rate

### Page Counts

```cpp
if (sampleNo < 4){ sampleSize = 22000; }
else if (sampleNo < 12){ sampleSize = 44000; }
else { sampleSize = 88000; }
```

- 0-3: 22000 samples (0.5s)
- 4-11: 44000 samples (1s)
- 12-15: 88000 samples (2s)

| Slot | Samples | Pages | Duration |
|---|---|---|---|
| 1–4 | 22,000 | 84 | ~0.5s |
| 5–12 | 44,000 | 167 | ~1.0s |
| 13–16 | 88,000 | 334 | ~2.0s |


### Upload Sequence

Implementation in `crc7.cpp`:

1. `AddStartMessage(sampleNo)` → slot select
2. For each page: `AddPage(data, pageAddr)` → 11 SysEx messages
3. `AddStopMessage()` → end transfer

### Audio Conversion

Input: `.wav` or `.aif` via JUCE `AudioFormatManager`.

Float samples are converted to 12-bit unsigned in `TanzmausSampleTool.cpp:208`. See [sysex.md](../sysex.md#sample-data-encoding) for the conversion formula. 

The tool does **not** resample, the file is sent at its native rate.


