#!/usr/bin/env bash
# VICE + NovaTerm for the peer-to-peer test, on the socat PTY.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
# Kill only THIS harness's emulator, by working directory -- never a bare
# pgrep -x x64sc, which would take out an emulator open for something else.
for p in $(pgrep -x x64sc); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *peer-vice*) kill "$p" 2>/dev/null;; esac
done
sleep 3
[ -e run/ttyC64 ] || { echo "FATAL: run/ttyC64 missing -- start-pty.sh first" >&2; exit 1; }
c1541 -format "xfer,01" d64 run/xfer.d64 >/dev/null 2>&1
[ -f payloads/PUNTEST.SEQ ] && c1541 -attach run/xfer.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1
DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    -rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400 \
    -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -drive10type 1541 -10 "$HERE/run/xfer.d64" \
    -autostart "$HOME/Documents/NovaTerm/novaterm_9.6c.d64" > /tmp/vice.log 2>&1 &
echo "VICE starting; give NovaTerm a moment to load"

# **Boot under -warp, then drop to 1x and PROVE it.**  The protocols are
# wall-clock: a C64 running 3x too fast is not a faster test, it is a broken
# one, and it reads as a protocol failure rather than as a speed problem.
sleep 28
cd "$HERE" && DISPLAY=:0 python3 vicewarp.py
