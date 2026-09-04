# Tanzmaus Sample Playback Rate

## What we know

- A 44.1 kHz file sounds at its original pitch when the tune knob is at **11 o'clock**
- This is the only absolute rate reference we have

## What we measured (at center knob position)

When we upload a file to the Tanzmaus without resampling, it gives the following results.  

| File rate | Source tone | Pitch with the tune knob at center |
|---|---|---|
| 44,100 Hz | A4 440 Hz | D5 +32c (sharp) |
| 48,000 Hz | A4 440 Hz | Db5 −14c (sharp) |
| 60,000 Hz | A4 440 Hz | A4 = 440 Hz (pitch-perfect) |

- With 44.1khz samples, center position applies a pitch boost relative to 11 o'clock
- The ratio K(center)/K(11) ≈ 1.3605 (+5.4 semitones)
- Delivering at 60 kHz gives pitch-perfect results at center

## What we don't know

- The machine's true internal sample rate (R_machine)
- K(center) and K(11) independently — only their ratio