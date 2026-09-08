# Tanzmaus Reverse-Engineering — Open Tasks

Actionable work remaining. Cross-references the docs in `reverse/` so it
defines *what to do next*, not *what is already known* (that lives in the
specs).

Legend: `[ ]` pending · `[x]` done

## 1. Hardware: Device photo verification [~done]
- [x] Open the device and take high-res photos of the MCU area
- [x] Transcribe SWD pads/header, BOOT0 resistor, chip mounting, part counts
- [ ] Answer the open questions left in [pcb-visual-analysis.md](reverse/pcb-visual-analysis.md):
- [x] Any silkscreen near the MCU (`SWD` / `ST-LINK` / `BOOT0` / `NRST` / `SWDIO`)? — **No**: checked under magnification, nothing readable near the MCU; no debug pins labeled
- [ ] Is the BOOT0 pin (LQFP48 pin 28) easily bridgeable to 3.3 V?
- [ ] Are the Adesto chips soldered or socketed; exact part under magnification?
- [ ] Confirm only one optocoupler; recount the 165/595 chips.
- [ ] (low priority) Identify the 4-pin SIP just above the MCU (likely a signal-isolation transformer or DC-DC module; not a memory/upload device — see [pcb-visual-analysis.md](reverse/pcb-visual-analysis.md))

The transcription is documented in `pcb-visual-analysis.md`; this decides
which hardware read paths are available.

## 2. Hardware: SOIC-8 clip on Adesto chips (dead-board, zero risk)
- [x] Verify `flashrom` with `ch341a_spi` backend is installed (v1.6.0)
- [x] Build `fw_dump_parse.py` for interpreting the raw dump
- [ ] Connect CH341A SPI programmer to one of the two Adesto chips
- [ ] Read JEDEC ID to confirm exact part — parts already identified from the datasheets by JEDEC (`1F 27 01` = AT45DB321E 32-Mbit, `1F 25 00` = AT45DB081E 8-Mbit; the "1610"/"1544" board marks are approximations), so the chip read is a confirmation, not an unknown
- [ ] Dump the raw contents (32-Mbit = 4 MiB or 8-Mbit = 1 MiB)
- [ ] This recovers the **sample/bank storage** and ties it to commands 0x05/06/07

## 3. Hardware: BOOT0 strap + ST ROM USART loader (near-zero risk)
- [ ] Bridge BOOT0 (LQFP48 pin 28) to 3.3 V, power up -> device enters ST ROM bootloader
- [ ] Connect STM32CubeProgrammer over USART1 (PA9/PA10) or USART2 (PD5/PD6)
- [ ] **Read-only full flash dump** — never send cmd 0x01 (OS upload) until restore-from-dump is possible
- [ ] Compare to our decoded image; check for bootloader region, extra bytes, and flash layout

This recovers the **internal-flash** bootloader + application. The hypothesis that a DataFlash chip holds the bootloader was assessed *unlikely* — see [firmware.md](reverse/firmware.md#could-a-dataflash-chip-hold-the-bootloader--assessed-unlikely) — so this dump reveals the internal bootloader region/layout, not the DataFlash contents.

## 4. Static: behavioral MIDI mapping (beyond the SysEx reply sweep)
`sysex-probes.md` already swept command bytes and confirmed the device
never replies (fire-and-forget). What remains is *behavioral* observation,
not reply probing:
- [ ] Send note-on/note-off, program change, and bank-select messages and observe audio behavior
- [ ] Map which messages trigger which sounds / change which parameters
- [ ] Exercise untested commands that may be *non-reply* but still act (e.g. safe `0x02–0x0A` payloads)
- [ ] Tie the observed behavior to the decoded MIDI CC table ([midi-cc.md](midi-cc.md))

## 5. Static: unresolved firmware fields
Tracked in detail in [firmware.md](reverse/firmware.md) "Remaining unknowns";
the items are addressed there, not duplicated here:
- [ ] Header signature fields — compare across versions, correlate with the STM32CubeProgrammer output format
- [ ] Footer words (`0x20000161`/`0x20000165` + `0x200000bc`) — analyze as potential boot-handoff metadata
- [ ] `ch[32] in {0,8}` — compare the stride-33 pattern across versions; see if it correlates with sample data or a specific memory region
- [ ] Establish **reachability** of the verified sample-decoder function at `0x08011D76` (no direct `BL` found — likely an indirect/jump-table dispatch) before wiring it to the live SysEx receiver — [firmware.md](reverse/firmware.md#sample-sysex-decode-path--genuine-executable-function-reachability-unproven)
- [ ] Resolve the **role** of the `0x08011736` MIDI/SysEx-shaped code region: prove or refute `r3 = USART1` via reachable CFG before accepting it as the MIDI receiver ([firmware.md](reverse/firmware.md#midisysex-shaped-code-region-at-0x08011736--pattern-verified-role-unproven)); bonus: turn the 6 walk-coherent TBB/TBH candidates into confirmed dispatch tables using `fw_cfg.py`'s switch resolution

The full list of unresolved function-level targets and the recommended
methodology (CFG construction, use-def tracing, version diffs) is in
[firmware.md](reverse/firmware.md) ("Static-analysis findings" and
"Remaining unknowns"; the CFG/method lives in `fw_cfg.py`).

## 5b. Bank-dump / factory-bank protocol
Tracking: [factory-patterns.md](reverse/factory-patterns.md) (our findings) and
[tanzmaus-reversing.md](reverse/tanzmaus-reversing.md) (mirror of the remote repo).
Decoder: `reverse/firmware-scripts/bankdump_decode.py`. Decoded blobs before banking:
`/tmp/fac`, `/tmp/base`, `/tmp/ai` (16 patterns × 3490 B each).
- [x] Decode the factory bank with the *correct* (convert_7to8) codec → 3490 B/pattern
- [x] Validate the codec against Windfisch's `all_instruments.syx` (BD + LFO step patterns)
- [x] Diff factory vs `bank-dump-baseline.syx` (8/16 identical: P05–P11, P13)
- [x] Characterize the 4 trailing frame bytes: deterministic `F(part, payload)`, per-frame
- [ ] Recover the exact `F(part, payload)` formula (standard CRC/sum families ruled out)
- [ ] Resolve `0d9e-0d9f` (pattern-level checksum?; no standard checksum matches)
- [ ] Resolve `0d96` (always 00 in factory bank) and the 8th laststep byte `01c7` (always 00)

---

## Priority order

```
1 (photos)  ->  decides everything else
2 (SOIC-8)  ->  most informative, zero risk, can do in parallel with 3
3 (BOOT0)   ->  full flash dump, safest path to bootloader reveal
4 (MIDI)    ->  requires device powered up, useful for validation
5 (static)  ->  can be interleaved throughout
```

## Safety notes
- **Never send cmd 0x01 (OS upload)** until a full flash dump enables restore
- SOIC-8 clip: dead-board only (no power), no risk to MCU
- BOOT0 strap: read-only ROM bootloader, no flash write unless explicitly commanded