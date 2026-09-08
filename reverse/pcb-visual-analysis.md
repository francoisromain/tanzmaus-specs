# Tanzmaus PCB — visual analysis

> Source: photo `mfb-tanzmaus-pcb.jpg` in this directory, with part markings transcribed manually.

## Device

- **MCU**: `STM32F303CCT6` (`GH933 9U CHN`) (12 pins per side, 7×7 mm, LQFP48 [datasheet](pcb-datasheet-STM32F303CCT6.md)).
- **Clock**: `ZTT 8.00MT`: 8 MHz ceramic resonator = HSE source. The app must configure RCC/PLL from this.
- **MIDI IN**: `H11L1` (6-pin white DIP) — Schmitt-trigger optocoupler, the classic MIDI input isolator. No second optocoupler reported → MIDI OUT is unisolated ("soft" TX), consistent with the fire-and-forget, simplex protocol.
- **4-pin SIP just above the MCU**: black plastic body ~1 cm long, ~5 mm tall, blank top, four metal pins in a single row (parallel to the MCU's top edge). Probably a small signal-isolation transformer or a SIP-4 DC-DC/power module. **Low relevance to firmware**: it's an analog/power part — not a memory device and not an upload/programming header (real STM32 update paths are USART1 via MIDI DIN and the BOOT0 ST-ROM loader). Unpinned; trace only if the analog/audio layer becomes a concern.

### STM32F303CCT6 — pinout & orientation

- Confirms the decoder's `0x2000A000` reading = exact SRAM top → the word at image offset `0x1ef` is a *genuine initial-SP value*, even though `0x1ef` cannot be a legitimate vector-table base (not 4-aligned).
- Authoritative peripheral base addresses for `fw_dispatcher.py` / any new analysis scripts; adds Flash interface `0x40022000` and CRC `0x40023000`.
- MIDI/USART identity: the app most plausibly targets **USART1 or USART2** (the only USARTs the ROM DFU loader uses, and the bases that cluster near the app's USART-shaped accesses).

The MCU package has its **pin-1 identification dot at the bottom-left corner** (photo verified). Text reads upright. This means the chip is mounted **90° CCW** relative to the datasheet's standard diagram (which shows pin 1 at top-left).

```text
                         TOP
             36  35  34  33  32  31  30  29  28  27  26  25
           ┌────────────────────────────────────────────────────┐
           │                                                    │
      37   │                                                    │   24
      38   │                                                    │   23
      39   │                                                    │   22
      40   │                                                    │   21
      41   │                                                    │   20
      42   │                                                    │   19
      43   │                                                    │   18
      44   │                                                    │   17
      45   │                                                    │   16
      46   │                                                    │   15
      47   │                                                    │   14
      48   │                                                    │   13
           └────────────────────────────────────────────────────┘
              1   2   3   4   5   6   7   8   9  10  11  12
                         BOTTOM
```


#### Physical edge mapping (your board)

| Datasheet edge (standard) | Your board edge | Pin range |
|---------------------------|-----------------|-----------|
| Top (37→48, right→left)   | **Left**        | 37–48 |
| Right (25→36, bottom→top) | **Top**         | 25–36 |
| Bottom (13→24, left→right)| **Right**       | 13–24 |
| Left (1→12, top→bottom)   | **Bottom**      | 1–12 |

#### Key pins on your physical board

| Function | Pin | Board edge | Position |
|----------|-----|------------|----------|
| **BOOT0** | **44** | left | 8th from top |
| **USART1_TX (PA9)** | **30** | top | 6th from left |
| **USART1_RX (PA10)** | **31** | top | 7th from left |
| **SWDIO (PA13)** | **34** | top | 3rd from left |
| **SWCLK (PA14)** | **37** | top | first |
| **NRST** | **7** | bottom | 7th from left |
| **GND (VSS)** | 23, 35, 47 | right, top, left | 2nd from top, 2nd from left, 2nd from bottom |



## External memory

Two Adesto 8-pin SOIC serial DataFlash chips (SPI), presumed sample/bank storage for the sample-based instruments (SP1/SP2):

| Marking | Part code | JEDEC ID | Part |
|---|---|---|---|
| `adesto1610` | `45DB 321E SHF` | `1F 27 01` | [AT45DB321E](pcb-datasheet-AT45DB321E.md) — 32-Mbit SPI DataFlash |
| `adesto1544` | `45DB 081E SHN` | `1F 25 00` | [AT45DB081E](pcb-datasheet-AT45DB081E.md) — 8-Mbit SPI DataFlash |

Hardware target of the sample-upload SysEx commands (`0x05`/`0x06`/`0x07`) and the SPI driver the firmware must contain.

## Support logic

| Marking | Package | Function |
|---|---|---|
| `NXP 74HCT165D CHMB82101 TXD16092` × many | 8-pin SO | Parallel-in serial-out shift register → panel buttons/encoders (input scan) |
| `NXP 74HC595D CKX16148 TnD1617d` × many | 8-pin SO | Serial-in parallel-out shift register → LEDs / display (output drive) |
| `79M05G` | 3–4 pin | 5 V regulator |
| `TS1117B` / `TS117D` | 3–4 pin | 3.3 V regulators |

## Power / passives

| Marking | Type |
|---|---|
| `SS14` (`6IY`) | 1 A / 40 V Schottky diode (SMA) — input polarity / protection |
| `C475` | small 2-pin SMD, marking `475` ⇒ ≈4.7 µF MLCC — decoupling |

## Analog / audio section

| Marking | Package | Function |
|---|---|---|
| `61A3DFUG3 LM13700M` | SO-16 (reported as "8 pins" = one side) | Dual operational transconductance amplifier (OTA) → VCA / voltage-controlled filter / waveshaper stage(s) |
| `53CTZYK TL064C` | SO-14 | Quad low-power JFET-input op-amp → audio buffers / mix / filter conditioning |

Classic output chain implied: MCU DAC (2-channel) → OTA VCA/filter (LM13700) → JFET-op-amp buffer/mix (TL064) → output. Relevant when mapping DAC writes statically (the analog drive/colour of the Tanzmaus lives here, outside the MCU).

## Consequences for the reverse engineering

- The two SPI DataFlash chips localize sample/bank persistence: read them (SOIC-8 clip + SPI programmer, dead-board, no power) to recover the sample storage layout and tie it to commands `0x05/06/07`.
- Static Tier-2 targets resolved: SPI1 `0x40013000` is the Adesto flash driver (SPI1->SR polling masks `0x80`/`0x600`; check the `.syx` for JEDEC-ID/read opcodes like `0x1F`/`0xBF`, `0x03`/`0x0B`) and USART1 `0x40013800` is the MIDI UART (BRR `0x900` = 31,250 baud; the H11L1 anchors MIDI-IN to a `PA`/`PD` USART-pin of USART1).
- 8 MHz HSE: look for PLL/clock literals in the RCC init sequence.
- The datasheet's CRC unit (EN/IEC 60335-1 style) suggested the firmware's tail words might be a global image signature — tested and returned **negative** (image-level CRC32/CRC16/XOR/sum never match a tail word; see `firmware.md` "Final frame").
- No on-board debug header / ST-Link reported, and **no silkscreen near the MCU** — hardware reads likely route via BOOT0 strapping (ST ROM USART loader) and/or the flash-chip clip, not an on-device SWD breakout; SWD remains physically possible only via unlabeled pins (LQFP48 **34=PA13/SWDIO**, **37=PA14/SWCLK**, VSS on **23/35/47**).

