# Tanzmaus SysEx reply-probe runbook

Empirical sweep to answer: **does the machine ever transmit a SysEx reply?**

## Wiring / ports

- Tanzmaus **MIDI IN**  <- MIDI4x4 "In 3" = `hw:2,0,2`
- Tanzmaus **MIDI OUT** -> MIDI4x4 "In 3" = `hw:2,0,2`  (same rawmidi node, IO)

So **sending** and **listening** use the same port `hw:2,0,2` (probe messages go out,
any replies come back in, both captured with `amidi`).

Preflight:

```sh
amidi -l                              # device must be present
fuser -v /dev/snd/midi*hw:*2* 2>/dev/null; ls -l /dev/snd/ | rg midi
```

If a DAW (Bitwig) has the port open you will see EBUSY on send; free it in the DAW
first (see `midi-debug.md`).

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

Run the machine fully booted, sequencer idle/stopped (same state as the successful
front-panel dump baseline `tanzmaus-tmp/bank-dump-baseline.syx`).

## Test A — Universal SysEx identity requests

```sh
cap ident-7F tanzmaus-specs/reverse/probes/ident-7F.syx
cap ident-0B tanzmaus-specs/reverse/probes/ident-0B.syx
cap ident-7D tanzmaus-specs/reverse/probes/ident-7D.syx
```

Any response looks like `F0 7E <id> 06 02 ... F7`.

## Test B — bank dump command over MIDI (the key one)

The front-panel dump is `F0 00 21 0B 04 00 03 <addr> <data> ... F7`. Does the machine
honour it **received over MIDI** (RX → TX, i.e. a reply path)?

```sh
cap dump-03-noarg tanzmaus-specs/reverse/probes/cmd03-noarg.syx
cap dump-03-zeroaddr tanzmaus-specs/reverse/probes/cmd03-zeroaddr.syx
```

If either produces a 67,280-byte capture (identical to the baseline dump) we have
our first empirically confirmed receive-initiated transmit.

## Test C — command-byte sweep

Envelope `F0 00 21 0B 04 00 <cmd> 00 01 F7`, one message per capture.
Curated low-risk set first, then full `00..7F` minus the dangerous/known ones
(`0x01` firmware upload — never send; `0x03` covered in Test B; `0x05/0x06/0x07`
sample uploads known silent).

```sh
for c in 00 02 04 08 10 20 40 7f; do
  cap sweep-$c "tanzmaus-specs/reverse/probes/sweep-$c.syx"
done
# optional full sweep
for c in 00 02 05 06 07 08 09 0a 0b 0c 0d 0e 0f 10 11 12 13 14 15 16 20 30 40 50 60 70 7f; do
  cap sweep-$c "tanzmaus-specs/reverse/probes/sweep-$c.syx"
done
```

## Test D — boot / idle sniff

Machine transmits nothing while idle (verified earlier). Re-power or reset the unit,
then record its MIDI OUT for 15 s:

```sh
amidi -p hw:2,0,2 -r /tmp/cap-boot.syx & p=$!; sleep 15; kill $p 2>/dev/null
stat -c%s /tmp/cap-boot.syx
```

A non-empty capture at boot = startup SysEx banner (a handshake/version poke we can use).

## Recording results

Fill the table below; results then get merged into
`tanzmaus-specs/reverse/firmware.md` under "Empirical probes".

| Test | Message | Bytes received | Reply? |
|---|---|---|---|
| A | ident-7F  | | |
| A | ident-0B  | | |
| A | ident-7D  | | |
| B | cmd03-noarg | | |
| B | cmd03-zeroaddr | | |
| C | sweep-00 … | | |
| D | boot sniff | | |