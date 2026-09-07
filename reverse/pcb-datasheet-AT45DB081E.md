# AT45DB081E — datasheet essentials

> [Source](pcb-datasheets/REN_DS-AT45DB081E-028N_DST_20260316.pdf) in this directory — Renesas
> document **DS-AT45DB081E-028 Rev. N**, 3/17/26. The **8-Mbit** member of the page-based
> DataFlash family (formerly Adesto/Atmel).

## Device

- **Part**: AT45DB081E — 8-Mbit DataFlash (**+ extra 256 kbits**), page-based SPI serial flash.
- **Page size**: **264 bytes (default)** or **256 bytes** (binary; factory pre-configurable), with
  **two fully independent SRAM data buffers** of the matching size.
- **Supply**: single **1.7 V – 3.6 V** — directly mates to the 3.3 V STM32F303.
- **Interface**: SPI (modes 0 and 3, RapidS™), **up to 85 MHz**, low-power read up to 15 MHz.
- **Temperature**: full **industrial temperature range**.
- **Packages**: 8-lead SOIC (**0.150" and 0.208"** wide), 8-pad ultra-thin DFN, WLCSP, wafer.

## Memory array

- **4096 pages** (0–4095) × 264 B = 1,081,344 B total (main 8-Mbit array at 264 B/page = 256 B +
  8 "extra" bytes/page; the extra 256 kbits is those 8 B × 4096 pages).
- Erase granularity: **Page** (264 B), **Block** (8 pages = **2 kB**), **Sector** (64 kB), **Chip**.
- Sector map: sector 0a = 8 pages, sector 0b = 248 pages, sectors 1–15 = 256 pages each.

## Command family (opcodes)

| Group | Opcodes |
|---|---|
| Continuous Array Read | `E8h` (legacy), `1Bh` / `0Bh` (high freq), `03h` (low freq), `01h` (low power) |
| Main Memory Page Read | `D2h` |
| Buffer Read | `D4h`/`D6h` (high freq), `D1h`/`D3h` (low freq), for buffer 1/2 |
| Buffer Write | `84h`/`87h` (buffer 1/2) |
| Buffer → Main Memory Page Program | `83h`/`86h` with erase, `88h`/`89h` without, buffer 1/2 |
| Direct page program | `82h`/`85h` (through buffer with built-in erase), `02h` (without erase) |
| Main Memory → Buffer transfer / compare | `53h`/`55h`, `60h`/`61h` |
| Status Register Read | `D7h` (RDY/BUSY, density, page-size bits) |
| Manufacturer & Device ID Read | `9Fh` → `1F 25 00 01 00` |

## JEDEC ID

| Byte | Value | Meaning |
|---|---|---|
| 1 | `1Fh` | Manufacturer = Renesas electronics (Adesto/Atmel legacy) |
| 2 | `25h` | Family `001` (AT45Dxxx) · density `00101` (**8-Mbit**) |
| 3 | `00h` | Sub/variant code |
| 4 | `01h` | EDI string length |
| 5 | `00h` | EDI byte |

## Reliability / power

- Endurance: **100,000** program/erase cycles/page minimum; data retention: **20 years**.
- Active read ~11 mA (typ @ 20 MHz); standby ~25 µA; deep power-down ~4.5 µA; ultra-deep ~400 nA.

## Relevance to the Tanzmaus RE

- This is the **smaller of the two sample-storage chips** on the PCB — `45DB 081E SHN` (marking
  "1544"). Together with the 32-Mbit AT45DB321E (`45DB 321E SHF`, marking "1610") it forms the
  SP1/SP2 sample/bank persistence (see [pcb-visual-analysis.md](pcb-visual-analysis.md)).
- **264-byte default page corroborates the firmware "Page size" finding** — the sample protocol's
  11 sub-frames × 24 samples = 264 samples/page (256 B mode would hold 256 samples/page) matches
  the DataFlash standard page exactly (firmware.md, "Page size — resolved"). The 264-byte page is
  the natural fit for the documented 264-sample pages.
- **Ground-truth JEDEC ID for the dead-board dump**: the CH341A + SOIC-8 clip read (`to-do.md` §2)
  should return `1F 25 00 01 00`. `fw_dump_parse.py --jedec=1F2500` and the rapid page-geometry /
  slot-capacity scan now have a concrete density target (1,048,576 B at 256 B/page, 1,081,344 B at
  264 B/page).
- The `AT45DB081E` is **not** in `fw_dump_parse.py`'s ID table (which lists the older D-series
  `AT45DB161D` 16-Mbit / `AT45DB041D` 4-Mbit) — the "1610"/"1544" markings had suggested ~16/4 Mbit;
  the actual parts are 32/8 Mbit. The table should gain `1F 27 01` and `1F 25 00`.
- Consistent with the SPI1 DataFlash driver finding (firmware.md, "Update bootloader"): status
  polling via `SPI1->SR` masks `0x80` (`SPIF`), `0x600` (`MODF`/`OVR`) — with a page-based part the
  host additionally polls the **D7h status-register RDY/BUSY bit** after program/erase, an opcode
  the firmware image scan can now be checked against.