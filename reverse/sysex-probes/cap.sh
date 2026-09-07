#!/bin/sh
# usage: cap.sh <label> <message.syx>
f=/tmp/cap-$1.syx
amidi -p hw:2,0,2 -r "$f" &
p=$!
sleep 0.5
amidi -p hw:2,0,2 -s "$2"
sleep 2
kill $p 2>/dev/null
if [ -s "$f" ]; then echo "$1: $(stat -c%s "$f") bytes RECEIVED"; xxd -p "$f"; else echo "$1: no data"; fi