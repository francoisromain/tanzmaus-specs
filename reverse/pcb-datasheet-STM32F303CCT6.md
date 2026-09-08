# STM32F303CCT6 — datasheet essentials

> [Source](pcb-datasheets/STM32F303CCT6-datasheet.pdf) in this directory — ST document **DS9118 Rev 14**,
> covering the STM32F303xB/xC family.

## Device

- **Part**: STM32F303CCT6 = STM32F303xC SKU in a **LQFP48** (7×7 mm) package.
- **Core**: Arm Cortex-M4F (FPU, DSP instructions, MPU), **72 MHz** max.
- **Memory** (Table 2, `Cx` SKU): 256 KB Flash, **40 KB SRAM on the data bus at `0x20000000`**, plus **8 KB CCM RAM at `0x10000000`**. SRAM top = `0x20000000 + 0xA000 = 0x2000A000`.
- **Analog**: 4× ADC, 2-channel DAC, 7 comparators, 4× op-amp (PGA).
- **Timers**: 2 advanced 16-bit, 5 general-purpose 16-bit, 1× 32-bit, 2 basic 16-bit.
- Packages: LQFP48/64/100 (and WLCSP100).

## Memory map highlights (Table 20)

| Address | Peripheral | Bus |
|---|---|---|
| `0x40013800` | USART1 | APB2 |
| `0x40004400` / `0x40004800` | USART2 / USART3 | APB1 |
| `0x40004C00` / `0x40005000` | UART4 / UART5 | APB1 |
| `0x40021000` | RCC | AHB1 |
| `0x40022000` | Flash interface | AHB1 |
| `0x40023000` | CRC unit | AHB1 |
| `0x40020000` / `0x40020400` | DMA1 / DMA2 | AHB1 |
| `0x48000000` … `0x48001800` | GPIOA … GPIOF | AHB2 |
| `0x50000000` … `0x500007FF` | ADC1-2 / ADC3-4 | AHB3 |
| `0x40014000` / `0x40014400` / `0x40014800` | TIM15 / TIM16 / TIM17 | APB2 |

## Boot modes (§3.5)

Boot0 pin + Boot1 option bit select: boot from **user Flash**, **system memory**, or **embedded SRAM**. The ST ROM bootloader (system memory) speaks DFU over **USART1 (PA9/PA10), USART2 (PD5/PD6), USB (PA11/PA12)**.

## CRC unit (§3.6)

Configurable generator polynomial and data size; the datasheet explicitly describes runtime-computed CRC signatures compared against a **reference signature generated at linktime and stored at a given memory location** (EN/IEC 60335-1 flash-integrity style).

## Package pin-numbering schema

The STM32F303CCT6 is housed in a 48-pin LQFP package with 12 pins on each side.

When viewing the **top of the chip**, with **pin 1 at the upper-left corner**, pin numbering proceeds **counter-clockwise** around the package:

```text
                              TOP
          48  47  46  45  44  43  42  41  40  39  38  37
        ┌────────────────────────────────────────────────────┐
        │                                                    │
   1    │                                                    │    36
   2    │                                                    │    35
   3    │                                                    │    34
   4    │                                                    │    33
   5    │                                                    │    32
   6    │                                                    │    31
   7    │                                                    │    30
   8    │                                                    │    29
   9    │                                                    │    28
  10    │                                                    │    27
  11    │                                                    │    26
  12    │                                                    │    25
        └────────────────────────────────────────────────────┘
          13  14  15  16  17  18  19  20  21  22  23  24
                            BOTTOM
```

### Pin ordering by physical side

| Physical side | Pin order | Direction when viewed from top |
|---|---|---|
| Left | 1 → 12 | Top → bottom |
| Bottom | 13 → 24 | Left → right |
| Right | 25 → 36 | Bottom → top |
| Top | 37 → 48 | Right → left |

### Pin 1

**Pin 1 is the uppermost pin on the left side** in the orientation shown above.

The package has a pin-1 identification mark. Once pin 1 is located, numbering proceeds counter-clockwise around the package.

### Left side — pins 1–12

Pins are ordered **top → bottom**.

| Pin | Function |
|---:|---|
| 1 | VBAT |
| 2 | PC13 |
| 3 | PC14 / OSC32_IN |
| 4 | PC15 / OSC32_OUT |
| 5 | PF0 / OSC_IN |
| 6 | PF1 / OSC_OUT |
| 7 | NRST |
| 8 | VSSA / VREF− |
| 9 | VDDA / VREF+ |
| 10 | PA0 |
| 11 | PA1 |
| 12 | PA2 |

### Bottom — pins 13–24

Pins are ordered **left → right**.

| Pin | Function |
|---:|---|
| 13 | PA3 |
| 14 | PA4 |
| 15 | PA5 |
| 16 | PA6 |
| 17 | PA7 |
| 18 | PB0 |
| 19 | PB1 |
| 20 | PB2 |
| 21 | PB10 |
| 22 | PB11 |
| 23 | VSS |
| 24 | VDD |

### Right side — pins 25–36

Pins are ordered **bottom → top**.

| Pin | Function |
|---:|---|
| 25 | PB12 |
| 26 | PB13 |
| 27 | PB14 |
| 28 | PB15 |
| 29 | PA8 |
| 30 | PA9 |
| 31 | PA10 |
| 32 | PA11 |
| 33 | PA12 |
| 34 | PA13 |
| 35 | VSS |
| 36 | VDD |

### Top — pins 37–48

Pins are ordered **right → left**.

| Pin | Function |
|---:|---|
| 37 | PA14 |
| 38 | PA15 |
| 39 | PB3 |
| 40 | PB4 |
| 41 | PB5 |
| 42 | PB6 |
| 43 | PB7 |
| 44 | BOOT0 |
| 45 | PB8 |
| 46 | PB9 |
| 47 | VSS |
| 48 | VDD |