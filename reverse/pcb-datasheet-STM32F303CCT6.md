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

Boot0 pin + Boot1 option bit select: boot from **user Flash**, **system memory**, or **embedded SRAM**. The ST ROM bootloader (system memory) speaks DFU over **USART1 (PA9/PA10), USART2 (PD5/PD6), USB (PA11/PA12)** — distinct from MFB's custom SysEx update protocol.

## CRC unit (§3.6)

Configurable generator polynomial and data size; the datasheet explicitly describes runtime-computed CRC signatures compared against a **reference signature generated at linktime and stored at a given memory location** (EN/IEC 60335-1 flash-integrity style). This first suggested the firmware's tail words might be a global image signature — tested and returned **negative** in the firmware analysis (image-level CRC32/CRC16/XOR/sum never match a tail word; see `firmware.md`, "Final frame").

## Relevance to the Tanzmaus RE

- Confirms the decoder's `0x2000A000` reading = exact SRAM top → the word at image offset `0x1ef` is a *genuine initial-SP value*, even though `0x1ef` cannot be a legitimate vector-table base (not 4-aligned).
- Authoritative peripheral base addresses for `fw_dispatcher.py` / any new analysis scripts; adds Flash interface `0x40022000` and CRC `0x40023000`.
- MIDI/USART identity: the app most plausibly targets **USART1 or USART2** (the only USARTs the ROM DFU loader uses, and the bases that cluster near the app's USART-shaped accesses).