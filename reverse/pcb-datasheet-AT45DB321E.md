# AT45DB321E — datasheet essentials

> [Source](pcb-datasheets/REN_DS-AT45DB321E-8784N_DST_20230831_1.pdf) in this directory — Renesas
> document **DS-AT45DB321E-8784 Rev. N**, 9/1/23. The **32-Mbit** member of the page-based
> DataFlash family (formerly Adesto/Atmel).

## Device

- **Part**: AT45DB321E — 32-Mbit DataFlash (**+ extra 1-Mbit**), page-based SPI serial flash.
- **Page size**: **528 bytes (default)** or **512 bytes** (binary; factory pre-configurable), with
  **two fully independent SRAM data buffers** of the matching size.
- **Supply**: single **2.3 V – 3.6 V**.
- **Interface**: SPI (modes 0 and 3, RapidS™), **up to 85 MHz**, low-power read up to 15 MHz.
- **Packages**: 8-lead SOIC (208-mil), 8-pad ultra-thin DFN, 8-pad DFN, wafer.

## Memory array

- **8192 pages** (0–8191) × 528 B = 4,325,376 B total (main 32-Mbit array at 528 B/page = 512 B +
  16 "extra" bytes/page; the extra 1 Mbit is those 16 B × 8192 pages).
- Erase granularity: **Page** (528 B), **Block** (8 pages = 4 kB), **Sector** (64 kB), **Chip**.
- Sector map: sector 0a = 8 pages, sector 0b = 120 pages, sectors 1–63 = 128 pages each.

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
| Manufacturer & Device ID Read | `9Fh` → `1F 27 01 01 00` |

## JEDEC ID

| Byte | Value | Meaning |
|---|---|---|
| 1 | `1Fh` | Manufacturer = Renesas electronics (Adesto/Atmel legacy) |
| 2 | `27h` | Family `001` (AT45Dxxx) · density `00111` (**32-Mbit**) |
| 3 | `01h` | Sub code `000` (standard series) · variant `00001` |
| 4 | `01h` | EDI string length |
| 5 | `00h` | EDI byte |

## Reliability / power

- Endurance: **100,000** program/erase cycles/page minimum; data retention: **20 years**.
- Active read ~7 mA; standby ~25 µA; deep power-down ~3 µA; ultra-deep ~400 nA.

## Relevance to the Tanzmaus RE

- This is the **larger of the two sample-storage chips** on the PCB — `45DB 321E SHF` (marking
  "1610"). Together with the 8-Mbit AT45DB081E (`45DB 081E SHN`, marking "1544") it forms the
  SP1/SP2 sample/bank persistence (see [pcb-visual-analysis.md](pcb-visual-analysis.md)).
- **528-byte default page corroborates the firmware "Page size" finding** — the sample protocol's
  264 samples/page × 2 bytes = **528 bytes** matches the DataFlash standard page exactly
  (firmware.md, "Page size — resolved", now confirmed against the shipped parts).
- **Ground-truth JEDEC ID for the dead-board dump**: the CH341A + SOIC-8 clip read (`to-do.md` §2)
  should return `1F 27 01 01 00`. `fw_dump_parse.py --jedec=1F2701` and the rapid page-geometry /
  slot-capacity scan now have a concrete density target (4,194,304 B at 512 B/page, 4,325,376 B at
  528 B/page).
- The `AT45DB321E` is **not** in `fw_dump_parse.py`'s ID table (which lists the older D-series
  `AT45DB161D` 16-Mbit / `AT45DB041D` 4-Mbit) — the "1610"/"1544" markings had suggested ~16/4 Mbit;
  the actual parts are 32/8 Mbit. The table should gain `1F 27 01` and `1F 25 00`.
- Consistent with the SPI1 DataFlash driver finding (firmware.md, "Update bootloader"): status
  polling via `SPI1->SR` masks `0x80` (`SPIF`), `0x600` (`MODF`/`OVR`) — with a page-based part the
  host additionally polls the **D7h status-register RDY/BUSY bit** after program/erase, an opcode
  the firmware image scan can now be checked against.