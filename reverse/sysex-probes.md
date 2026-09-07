# Tanzmaus SysEx reply-probe runbook

Empirical sweep to answer: **does the machine ever transmit a SysEx reply?**

## Wiring / ports

- Tanzmaus **MIDI IN**  <- MIDI4x4 "In 3" = `hw:2,0,2`
- Tanzmaus **MIDI OUT** -> MIDI4x4 "In 3" = `hw:2,0,2`  (same rawmidi node, IO)

So **sending** and **listening** use the same port `hw:2,0,2` (probe messages go out, any replies come back in, both captured with `amidi`).

Preflight:

```sh
amidi -l                              # device must be present
fuser -v /dev/snd/midi*hw:*2* 2>/dev/null; ls -l /dev/snd/ | rg midi
```

If a DAW (Bitwig) has the port open you will see EBUSY on send; free it in the DAW first.

## Capture-and-send helper

```sh
# usage: cap <label>
cap() {
  local f=/tmp/cap-$1.syx
  amidi -p hw:2,0,2 -r "$f" & local p=$!
  sleep 0.5
  amidi -p hw:2,0,2 -s "$2"
  sleep 2
  kill "$p" 2>/dev/null
  if [ -s "$f" ]; then echo "$1: $(stat -c%s "$f") bytes RECEIVED"; xxd -p "$f"; else echo "$1: no data"; fi
}
```

Run the machine fully booted, sequencer idle/stopped (same state as the successful front-panel dump baseline `sysex-probes/bank-dump-baseline.syx`).

## Test A — Universal SysEx identity requests

```sh
cap ident-7F tanzmaus-specs/reverse/sysex-probes/ident-7F.syx
cap ident-0B tanzmaus-specs/reverse/sysex-probes/ident-0B.syx
cap ident-7D tanzmaus-specs/reverse/sysex-probes/ident-7D.syx
```

Any response looks like `F0 7E <id> 06 02 ... F7`.

## Test B — bank dump command over MIDI (the key one)

The front-panel dump is `F0 00 21 0B 04 00 03 <addr> <data> ... F7`. Does the machine honour it **received over MIDI** (RX → TX, i.e. a reply path)?

```sh
cap dump-03-noarg tanzmaus-specs/reverse/sysex-probes/cmd03-noarg.syx
cap dump-03-zeroaddr tanzmaus-specs/reverse/sysex-probes/cmd03-zeroaddr.syx
```

If either produces a 67,280-byte capture (identical to the baseline dump) we have our first empirically confirmed receive-initiated transmit.

## Test C — command-byte sweep

Envelope `F0 00 21 0B 04 00 <cmd> 00 01 F7`, one message per capture. Curated low-risk set first, then full `00..7F` minus the dangerous/known ones (`0x01` firmware upload — never send; `0x03` covered in Test B; `0x05/0x06/0x07` sample uploads known silent).

```sh
for c in 00 02 04 08 10 20 40 7f; do
  cap sweep-$c "tanzmaus-specs/reverse/sysex-probes/sweep-$c.syx"
done
# optional full sweep
for c in 00 02 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 20 30 40 50 60 70 7f; do
  cap sweep-$c "tanzmaus-specs/reverse/sysex-probes/sweep-$c.syx"
done
```

## Test D — boot / idle sniff

Machine transmits nothing while idle (verified earlier). Re-power or reset the unit, then record its MIDI OUT for 15 s:

```sh
amidi -p hw:2,0,2 -r /tmp/cap-boot.syx & p=$!; sleep 15; kill $p 2>/dev/null
stat -c%s /tmp/cap-boot.syx
```

A non-empty capture at boot = startup SysEx banner (a handshake/version poke we can use).

## Recording results

**Completed 2026-09-06 — verdict: fire-and-forget.** The machine never transmits SysEx in response to a received message. All 13 probes returned zero bytes:

| Test | Message | Bytes received | Reply? |
|---|---|---|---|
| A | ident-7F (`F0 7E 7F 06 01 F7`) | 0 | No |
| A | ident-0B (`F0 7E 0B 06 01 F7`) | 0 | No |
| A | ident-7D (`F0 7E 7D 06 01 F7`) | 0 | No |
| B | cmd03-noarg (`F0 00 21 0B 04 00 03 F7`) | 0 | No |
| B | cmd03-zeroaddr (`F0 00 21 0B 04 00 03 00 01 F7`) | 0 | No |
| C | sweep-00 (`F0 00 21 0B 04 00 00 00 01 F7`) | 0 | No |
| C | sweep-02 | 0 | No |
| C | sweep-04 | 0 | No |
| C | sweep-08 | 0 | No |
| C | sweep-10 | 0 | No |
| C | sweep-20 | 0 | No |
| C | sweep-40 | 0 | No |
| C | sweep-7F | 0 | No |

Notes:

- The bank dump (`cmd 0x03`) is the only proven TX path, triggered via front-panel Shift+Step 9 and preserved in `sysex-probes/bank-dump-baseline.syx` (67,280 bytes, shell `F0 00 21 0B 04 00 03 …` — note: the real capture is `04 00 03`, i.e. the transfer-class bytes `04 00` are part of the header). Sending it over MIDI produces no response — confirming the dump path is front-panel-gated only.
- The Universal SysEx identity protocol is not supported.
- The curated command sweep tested representative bytes across the `0x00..0x7F` range; no response to any.
- A boot/idle sniff was not performed (the machine transmits nothing while idle, consistent with the fire-and-forget finding above).
- Handshaking/blocking changes remain on hold pending the author's decision.

Re-running the sweep above should produce the same outcome.