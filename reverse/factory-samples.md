# MFB Tanzmaus — Factory Samples

[Source](../mfb/factory_samples/)

## File specs

32 WAV files, 48 kHz, mono, 16-bit

| Files | Frames | Duration |
|---|---|---|
| 1–8 | 24,000 | 0.5 s |
| 9–24 | 48,000 | 1.0 s |
| 25–32 | 96,000 | 2.0 s |


## 48 kHz vs 44.1 kHz issue

The machine plays samples at 44.1 kHz. Factory samples are 48 kHz.

When uploaded with the official tool (without resampling), the sounds play ~1.5 semitones sharp.


## Slot mapping

Make the samples fit the [slots capacity](../sysex.md#slot-lengths).  

| File | Slot | File | Slot | File | Slot |
|---|---|---|---|---|---|
| 1 | SP1/1 | 9 | SP1/5 | 25 | SP1/13 |
| 2 | SP1/2 | 10 | SP1/6 | 26 | SP1/14 |
| 3 | SP1/3 | 11 | SP1/7 | 27 | SP1/15 |
| 4 | SP1/4 | 12 | SP1/8 | 28 | SP1/16 |
| | | 13 | SP1/9 | | |
| | | 14 | SP1/10 || |
| | | 15 | SP1/11 || |
| | | 16 | SP1/12 || |
| |
| 5 | SP2/1 | 17 | SP2/5 |29 | SP2/13 |
| 6 | SP2/2 | 18 | SP2/6 | 30 | SP2/14 |
| 7 | SP2/3 | 19 | SP2/7 | 31 | SP2/15 |
| 8 | SP2/4 | 20 | SP2/8 | 32 | SP2/16 |
| | | 21 | SP2/9 | | |
| | | 22 | SP2/10 | | |
| | | 23 | SP2/11 | | |
| | | 24 | SP2/12 | | |
