# MFB Tanzmaus — MIDI CC Assignments

CC numbers for the Tanzmaus sound/voice parameters, extracted from the manual appendix ("MIDI Implementation / MIDI Controller assignment").

The MIDI channel for controller data is always the same as the channel of the corresponding instrument, selected with the MIDI Learn function.

## BD

| CC | Function |
|----|----------|
| 2 | Attack |
| 3 | Tune |
| 4 | Noise |
| 5 | Noise Decay |
| 6 | Dist |
| 64 | Decay |
| 65 | Pitch |
| 66 | Trigger |

## SD

| CC | Function |
|----|----------|
| 11 | Tune |
| 13 | Noise |
| 67 | Noise Decay |
| 70 | Trigger |
| 71 | Decay Tone |

## CP (Clap)

| CC | Function |
|----|----------|
| 18 | Filter |
| 75 | Decay |
| 76 | Attack |
| 77 | Trigger |

## TT (Tom)

| CC | Function |
|----|----------|
| 19 | Tune |
| 20 | Decay |
| 73 | Pan |
| 78 | Trigger |
| 79 | Attack |
| 82 | Pitch |

## SAMPLE1

| CC | Function |
|----|----------|
| 84 | Tune |
| 85 | Decay |
| 86 | Sample Select 1 |
| 87 | Sample Select 2 |
| 88 | Attack |

## SAMPLE2

| CC | Function |
|----|----------|
| 89 | Tune |
| 90 | Decay |
| 91 | Sample Select 1 |
| 92 | Sample Select 2 |
| 93 | Attack |

## MIDI data the Tanzmaus responds to

- System Realtime: `MIDI_CLOCK`, `MIDI_START`, `MIDI_CONTINUE`, `MIDI_STOP`.
- Channel Messages: `MIDI_NOTE_ON`, `MIDI_NOTE_OFF`, `MIDI_CONTROLLER`, `MIDI_PROG_CHANGE` (0...63).
- `MIDI_SYSEX`
- `MIDI_SONG_POSITION_POINTER`.
