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
| 1 | sp1/1 | 9 | sp1/5 | 25 | sp1/13 |
| 2 | sp1/2 | 10 | sp1/6 | 26 | sp1/14 |
| 3 | sp1/3 | 11 | sp1/7 | 27 | sp1/15 |
| 4 | sp1/4 | 12 | sp1/8 | 28 | sp1/16 |
| | | 13 | sp1/9 | | |
| | | 14 | sp1/10 || |
| | | 15 | sp1/11 || |
| | | 16 | sp1/12 || |
| |
| 5 | sp2/1 | 17 | sp2/5 |29 | sp2/13 |
| 6 | sp2/2 | 18 | sp2/6 | 30 | sp2/14 |
| 7 | sp2/3 | 19 | sp2/7 | 31 | sp2/15 |
| 8 | sp2/4 | 20 | sp2/8 | 32 | sp2/16 |
| | | 21 | sp2/9 | | |
| | | 22 | sp2/10 | | |
| | | 23 | sp2/11 | | |
| | | 24 | sp2/12 | | |
