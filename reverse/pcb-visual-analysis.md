# Tanzmaus PCB — visual analysis

> Source: photo `mfb-tanzmaus-pcb.jpg` in this directory, with part markings transcribed manually.

## Device

- **MCU**: `STM32F303CCT6` (`GH933 9U CHN`) (12 pins per side, 7×7 mm, LQFP48 [datasheet](pcb-datasheet-STM32F303CCT6.md)).
- **Clock**: `ZTT 8.00MT`: 8 MHz ceramic resonator = HSE source. The app must configure RCC/PLL from this.
- **MIDI IN**: `H11L1` (6-pin white DIP) — Schmitt-trigger optocoupler, the classic MIDI input isolator. No second optocoupler reported → MIDI OUT is unisolated ("soft" TX), consistent with the fire-and-forget, simplex protocol.

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
- No on-board debug header / ST-Link reported — hardware reads likely route via BOOT0 strapping (ST ROM USART loader) and/or the flash-chip clip, not SWD.

## Open questions

1. Any silkscreen near the MCU (`SWD` / `ST-LINK` / `BOOT0` / `NRST` / `SWDIO`)?
2. BOOT0 strap: is the MCU's BOOT0 pin (LQFP48 pin 28) resistor easily bridgeable to 3.3 V?
3. Adesto chips soldered or socketed? (parts identified: AT45DB321E / AT45DB081E)
4. Confirm only one optocoupler (MIDI OUT unisolated) and count of 165/595 chips.
