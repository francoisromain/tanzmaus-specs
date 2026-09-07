# Tanzmaus Bank/Pattern Dump Protocol

Analysis of the Tanzmaus **bank dump** SysEx protocol (device → host bulk read of all pattern/song data), based on the [Windfisch/tanzmaus-reversing](https://github.com/Windfisch/tanzmaus-reversing) project.

## Transport Protocol

A bank dump is a burst of SysEx messages. Frame structure (all offsets byte-indexed from `F0`):

```
F0  00 21 0B  04 00 03 00 00  <part>  [<pattern> 00]  <payload7...>  <4 trailing>  F7
│   │───────│  │────────────│  │       │───────────│   │─────────│   │──────────│   │
│    MFB ID     transfer+cmd   │        pattern no.    7-bit data    stripped    │
│         (04 00) (03=bank     │   (only when          payload                F7
│          dump)     part==0)  │    part==0)                           (end)
│                              │  sequence counter

byte   0:  F0            (SysEx begin)
bytes 1-3: 00 21 0B      (MFB manufacturer SysEx ID)
bytes 4-8: 04 00 03 00 00
             04 00       (transfer class)
             03          (bank dump command)
             00 00
byte   9:  part          (sequence counter 0..13=0x0D, wraps to 0)
byte  10:  pattern       (pattern no. 0..15, present only when part==0)
byte  11:  00
bytes 12..: payload      (7-bit encoded, see below)
last 4 bytes:            (stripped as a possible checksum)
last byte :  F7          (SysEx end)
```

### Pattern of frames

Each of the 16 patterns is sent as **14 messages**:

- **13 messages of 317 bytes** (`part` = 0..12)
- **1 message of 84 bytes** (`part` = 13 = 0x0D)

Sequence: `part` counts 0 → 13, wraps; `pattern` increments whenever `part` wraps to 0. Verified for all messages in `all_instruments.syx` (224 frames total; `part` counters 0x00..0x0D each appear exactly 16×).

### 7-bit to 8-bit decoding

MIDI data bytes carry only 7 payload bits, so the raw payload is re-packed:

1. **7→8 pack**: take 8 bytes of 7 bits → concatenate 56 bits → re-split into 7 bytes of 8 bits (see `convert_7to8` in `util.py`; MSB-first with each byte fed LSB-first per bitorder experiment).
2. **Bit mirror**: reverse the bit order of every resulting byte (`bitmirror` in `util.py`).

The first 16 bits of each pattern are the pattern id + `00`, and are stripped so the step data starts at offset 0.

---

## Pattern Data Layout (0xDA2 = 3490 bytes per pattern)

Decoded map (from `README.md` and `parse_pattern.py`; box notation `xx - yy` = inclusive byte range):

```
0000 - 01bf  step data: 16x 2-byte A pattern + 16x 2-byte B pattern,
              for BD, SD, RS, CP, TT, SP1, SP2 in that order (7 instruments,
              0x40 bytes each: 32 steps x 2 bytes)
01c0 - 01c7  bitmirrored "last step" values  (8 entries; identity of the 8th unresolved)
01c8 - 01d0  mute state for bd, sd, rs, cp, tt, sp1, sp1alt, sp2, sp2alt
              0x80 = muted vs 00 (no LFOS)
01d1 - 01d4  mute state for bdlfo, cplfo, ttlfo, sp1lfo
01d5 - 02b4  flam data
02b5         00
02b6 - 0a75  knob data: BD, SD, SP1, SP2, CP, TT in that order
0a76 - 0d95  LFO data: BD, CP, TT, SP1, SP2 in that order,
              5 blocks x 0xa0 bytes, each 5 sub-blocks of 0x20:
              +00  step data: 32 x 1 byte, 0x00=off / 0x01 / 0x02 / 0x03
              +20  amount: 2-byte little-endian words (16 confirmed per
                   block; likely 32 spanning the next sub-block - unconfirmed)
              +40  always 0x00 in this dump (unconfirmed)
              +60  speed: 32 x 1 byte, values in the 0x04..0x0c range,
                   subset matching {00 30 20 18 10 0c 08 06 05 04 03 01}
              +80  waveform?: 32 x 1 byte, sparse values 0x01/0x02/0x03
              (confirmed against bank-dump-baseline.syx, all 16 patterns)
0d96         ?? TODO
0d97         tempo multiplier / scale (0x60=16ths, 0x30=8ths)
0d98         sp2 lfo mute (80 vs 00)
0d99         00
0d9a         bitmirrored shuffle value
0d9b - 0d9d  00 00 00
0d9e - 0d9f  checksum?  (2 bytes)
0da0 - 0da1  00 00
```

Per-instrument step data blocks:

| Instrument | Step range | Knob data range | Knob stride |
|---|---|---|---|
| BD  | 0000 - 003f | 02b6 - 0435 | 32 x 12 bytes |
| SD  | 0040 - 007f | 0436 - 0535 | 32 x 8 bytes |
| RS  | 0080 - 00bf | — | — |
| CP  | 00c0 - 00ff | 0836 - 0935 | 32 x 8 bytes |
| TT  | 0100 - 013f | 0936 - 0a75 | 32 x 10 bytes |
| SP1 | 0140 - 017f | 0536 - 06b5 | 32 x 12 bytes |
| SP2 | 0180 - 01bf | 06b6 - 0835 | 32 x 12 bytes |

LFO blocks (each 0xa0 bytes, 5 sub-blocks of 0x20): step data, amount (2-byte LE words), then +0x40 (always zero in this dump), +0x60 (likely speed) and +0x80 (likely waveform) — see the map above. Block starts:

```
bdlfo  0a76   cplfo  0b16   ttlfo  0bb6   sp1lfo  0c56   sp2lfo  0cf6
```

The block structure and the fields above were confirmed against `bank-dump-baseline.syx` (all 16 patterns); the exact meaning of the +0x40/+0x60/+0x80 sub-blocks is not fully resolved.

### Encodings learned

- Accent: `(1,2,3,4,off)` = `(0fff, 0be8, 0800, 05dc, 0000)`
- Knob values are stored bit-reversed (verified via the "BD increasing tune" trace in `README.md`)
- `sampleOrAlt` = 00/01 for SP1, 02/03 for SP2
- Sweet-spot byte `!!` before `decay` = 00/01 for SP1, 16/17 for SP2 (sound index?)

---

## Tool Usage

Capturing a bank dump from hardware:

```sh
amidi -p $PORT -r file.syx       # capture, end with ^C
python3 parse_bankdump.py file.syx PATTERN_NUMBER OUT.bin   # one pattern
python3 parse_pattern.py  file.syx PATTERN_NUMBER           # tracker view
```

---

## Shared Header

The bank dump uses the same MFB SysEx shell as the other Tanzmaus sub-commands: header prefix `F0 00 21 0B 04 00`, command byte `0x03` (bank dump) distinct from the firmware `0x01` and sample `0x05`/`0x06`/`0x07` commands. 

Device ID `0x0B` is hardcoded throughout.

---

## Outstanding Unknowns

- LFO block internals: the exact amount width (16 confirmed 2-byte LE words; a second half in the always-zero +0x40 sub-block would make 32), the speed vocabulary (`0x09`, `0x60` are not in the documented speed map), and the waveform field size (31 vs 32). Needs captures with LFOs explicitly programmed.
- 1 unknown byte at `0d96`
- 7 always-zero(?) bytes
- 2 bytes at `0d9e-0d9f` that might be a checksum (in this dump: `6b 32`)
- the identity of the 8th mirrored "last step" value at `01c0-01c7`
