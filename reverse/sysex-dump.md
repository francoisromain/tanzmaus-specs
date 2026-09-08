# Factory Pattern Bank — Decode & Analysis

Findings from the **factory bank dump**, decoded with the correct bank-dump codec (`convert_7to8` from [tanzmaus-reversing.md](tanzmaus-reversing.md)). This file documents what *we* verified / discovered beyond the remote Windfisch repo.

## Source files

| File | Description |
|---|---|
| `mfb/tanzmaus 1-16 factory patterns.syx` | Factory bank dump captured from a stock instrument (224 frames) |
| `reverse/sysex-probes/bank-dump-baseline.syx` | Front-panel dump of the *same* device for diffing |
| `reverse/firmware-scripts/bankdump_decode.py` | Our decoder: validates framing, converts 7→8, splits 16 patterns ×3490 B |

Validation captures (`all_instruments.syx`, Windfisch's notebook examples) are fetched transiently to `/tmp` only and not vendored.

## Correct decode recipe

A bank dump (cmd `0x03`) is **not** decoded with the firmware varint (`unpack7`, that one is LSB-first). It uses per-frame:

1. Split on `F0`; validate `F7` terminator, MFB id `00 21 0B`, header `04 00 03 00 00`.
2. `part` = byte 9 validates as a strict 0→13 counter.
3. Payload = frame `[10:-1]`, with the **last 4 bytes stripped** (trailing derived value, see below).
4. `convert_7to8`: concatenate the *reversed* low-7-bit of each byte, re-slice into 8-bit bytes.
5. Per pattern: 13 frames of 317 B (parts 0..12 → 264 B each) + 1 frame of 84 B
   (part 0x0D → 60 B) = 3492 raw bytes.
6. Strip the first 16 bits (pattern id + `00`) → **3490 B = 0xDA2** per pattern.

An earlier firmware-based decode produced 3534 B/pattern (wrong alignment); all numbers in
this file use the 3490-B decode above.

### Framing verified (224 frames)

- 208 long frames (317 B, parts 0–12) + 16 short frames (84 B, part 0x0D) — every part 0–13 exactly 16×.
- All headers `F0 00 21 0B 04 00 03 00 00`; `part` counts 0→13 and wraps.
- Pattern id (byte 10) is present only at `part==0`, values 0..15 once each; byte 11 is always 00.

## Codec validation

- Pattern 0 of `all_instruments.syx`: BD steps on 1,3,5,7,9,10,11,12,13,14,15,16 (`ff f0`) exactly as documented in Windfisch's notebook.
- LFO step data for `all_instruments.syx` patterns 1 (BDlfo), 5 (CPlfo), 10 (SP1lfo), 13 (SP2lfo): 0x80 at steps 1,3,5,7,9,10,11,12,13,14,15,16 — matches the notebook.

## Factory readout (all 16 patterns)

Per-pattern active-step counts (32-step grid, A/off bit set):

| Pat | BD | SD | RS | CP | TT | SP1 | SP2 |
|-----|----|----|----|----|----|-----|-----|
| 00  | 4  | 2  | 0  | 0  | 2  | 4   | 9   |
| 01  | 3  | 0  | 5  | 2  | 0  | 8   | 2   |
| 02  | 4  | 3  | 0  | 2  | 4  | 4   | 4   |
| 03  | 4  | 2  | 7  | 0  | 0  | 8   | 2   |
| 04  | 4  | 0  | 0  | 2  | 0  | 9   | 0   |
| 05  | 6  | 0  | 0  | 2  | 0  | 11  | 10  |
| 06  | 5  | 2  | 0  | 8  | 6  | 0   | 6   |
| 07  | 4  | 0  | 2  | 0  | 0  | 6   | 16  |
| 08  | 6  | 7  | 0  | 2  | 2  | 8   | 10  |
| 09  | 2  | 4  | 0  | 1  | 4  | 5   | 4   |
| 10  | 4  | 2  | 0  | 2  | 0  | 10  | 4   |
| 11  | 5  | 12 | 0  | 3  | 0  | 4   | 6   |
| 12  | 2  | 1  | 0  | 2  | 0  | 0   | 8   |
| 13  | 4  | 0  | 0  | 2  | 0  | 12  | 4   |
| 14  | 5  | 2  | 0  | 0  | 3  | 4   | 2   |
| 15  | 4  | 6  | 0  | 0  | 0  | 8   | 5   |

LFO step on-counts (32-step):

| Pat | BDlfo | CPlfo | TTlfo | SP1lfo | SP2lfo |
|-----|-------|-------|-------|--------|--------|
| 00  | 0 | 0 | 0 | 0 | 0 |
| 01  | 0 | 2 | 0 | 0 | 0 |
| 02  | 0 | 0 | 0 | 0 | 0 |
| 03  | 0 | 0 | 0 | 0 | 1 |
| 04  | 0 | 0 | 0 | 0 | 1 |
| 05  | 0 | 0 | 0 | 0 | 0 |
| 06  | 0 | 0 | 0 | 0 | 4 |
| 07  | 0 | 0 | 0 | 0 | 9 |
| 08  | 0 | 0 | 0 | 0 | 0 |
| 09  | 2 | 1 | 0 | 0 | 0 |
| 10  | 0 | 1 | 0 | 0 | 0 |
| 11  | 0 | 3 | 0 | 2 | 0 |
| 12  | 0 | 0 | 0 | 0 | 0 |
| 13  | 4 | 3 | 0 | 1 | 0 |
| 14  | 0 | 3 | 0 | 1 | 1 |
| 15  | 0 | 3 | 0 | 0 | 1 |

Shared tail fields (all 16 patterns):

- `0d96` = `00` (still unknown)
- `0d97` (scale) = `0x60` (16ths) for all 16
- `0d98` (sp2 lfo mute) = `00` for all 16
- `0d9a` (shuffle) = `0x20` for P05–P08, `00` for all others
- laststeps (`01c0-01c7`) = `f0 f0 f0 f0 f0 f0 f0 00` for all 16 — the 8th value is `00`, not `f0` (identity still unresolved)
- `0d9e-0d9f` (checksum?) varies per pattern; see below

## Factory vs baseline diff

Factory patterns that are **byte-identical** to the live front-panel dump (`bank-dump-baseline.syx`, decode-independent):

```
P05  P06  P07  P08  P09  P10  P11  P13      (8 of 16)
```

Differing patterns and where they differ (bytes changed, by region):

| Pat | steps+laststeps | flam | knobs | LFO | tail |
|-----|-----------------|------|-------|-----|------|
| P00 | 60  | — | 920 | — | 3 |
| P01 | 83  | — | 649 | 13 | 3 |
| P02 | 65  | — | 588 | 7 | 2 |
| P03 | 34  | — | 979 | 5 | 2 |
| P04 | 61  | — | 552 | 5 | 3 |
| P12 | 87  | — | 1224 | 10 | 2 |
| P14 | 95  | 10 | 1136 | 76 | 3 |
| P15 | 65  | — | 1070 | 67 | 2 |

Knob/step/LFO differences dominate; the differing region (base unit `0x00` vs factory value) is consistent with the front panel shipping with a different (edit) state than factory.

## The 4 trailing bytes per frame

Each frame ends with 4 data bytes before `F7` (e.g. part-0 frame: `00 19 01 1b`).

What we established:

- They are **deterministic**: the same `(part, payload)` yields the same trailing 4 bytes (checked across all 224 factory frames and across identical factory↔baseline patterns).
- They are **not cumulative**: frames at the same `part` with identical (all-zero) payload produce the same value in *different* patterns with different earlier content — so the value is a function of the *current* frame only.
- All-zero payloads give a per-part constant:

| part | trailing bytes |
|------|----------------|
| 4  | `00 2a 00 21` |
| 5  | `01 0a 01 11` |
| 8  | `00 2d 00 6b` |
| 9  | `01 0d 01 5b` |
| 10 | `00 2c 00 08` |
| 11 | `01 0c 01 38` |
| 12 | `00 2f 01 2d` |

- They look like two 14-bit big-endian 7-bit values (each byte pair `<h> <l>`, h∈{00,01}, i.e. MIDI-safe). Not a 28-bit checksum.

Ruled out (computed over raw-7 payload, decoded-8 payload, bit-mirrored variants, and with the `part` byte prepended/appended in various positions): simple sum/xor/LRC, CRC-8, CRC-16 (ARC, MODBUS, CCITT-FALSE, KERMIT, XMODEM, X25, AUG-CCITT, DNP), CRC-24, CRC-32 (standard/reflected/CRC-32C), Fletcher-16, base-128 digit-sums, and strided/weighted byte-sums. **No standard checksum in a bit space tried reproduces the value.**

Conclusion: the trailing 4 bytes are a deterministic, per-frame derived value `F(part, payload)` — most likely a firmware-side checksum/hash whose exact algorithm wasn't recovered from the dump alone. This is still an **open question**.

## The `0d9e-0d9f` field

Varies per pattern and does not match any standard checksum of the 3490-byte pattern (same families as above, with the field excluded). Also unresolved.

## Open questions

- The exact `F(part, payload)` formula for the 4 trailing bytes.
- The meaning of `0d9e-0d9f` (pattern-level checksum? format-dependent?).
- The identity/meaning of `0d96` (always `00` in the factory bank).
- The 8th "last step" byte at `01c7` (always `00` in the factory bank).