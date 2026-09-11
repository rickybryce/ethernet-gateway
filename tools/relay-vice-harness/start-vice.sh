#!/usr/bin/env bash
# Start VICE + NovaTerm for one LINK and leave it up across many transfers.
#   ./start-vice.sh serial|telnet
#
# The emulator is restarted only when the LINK changes: the ACIA is wired to a
# PTY for serial and to tcpser's ip232 socket for telnet, and that is a
# command-line choice.  Within a link NovaTerm keeps running -- `relay-one.sh`
# re-establishes the state it needs at the top of every transfer (C= Z back to
# the menu, hangup PROVED by AT/OK rather than assumed, protocol re-selected),
# which is what makes a per-transfer restart unnecessary.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
LINK="${1:-serial}"

# Kill only THIS harness's emulator -- identified by its working directory,
# never a bare `pgrep -x x64sc`, which would take out an emulator someone has
# open for something else.
for p in $(pgrep -x x64sc); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *relay-vice*) kill "$p" 2>/dev/null;; esac
done
sleep 3

if [ "$LINK" = serial ]; then
    [ -e run/ttyC64 ] || { echo "FATAL: run/ttyC64 missing -- start the slave first" >&2; exit 1; }
    RS=(-rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400)
else
    RS=(-rsdev1 "127.0.0.1:25232" -rsdev1ip232 -rsdev1baud 2400)
fi

c1541 -format "xfer,01" d64 run/xfer.d64 >/dev/null 2>&1
c1541 -attach run/xfer.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1

DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    "${RS[@]}" -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -drive10type 1541 -10 "$HERE/run/xfer.d64" \
    -autostart "$HOME/Documents/NovaTerm/novaterm_9.6c.d64" > /tmp/vice.log 2>&1 &
echo "VICE started on the $LINK link; waiting for NovaTerm's main menu"

# Wait for NovaTerm to finish loading before touching anything.  The menu is
# the only honest signal: a fixed sleep either wastes time or types into a
# splash screen, and the emulator boots at a different speed on every host.
for i in $(seq 1 12); do
    r=$(DISPLAY=:0 timeout 40 python3 -c "
import novaterm
nt=novaterm.NovaTerm(); s=nt.selected()
print(novaterm.MAIN_ITEMS[s] if s is not None else 'loading')" 2>/dev/null \
        | grep -v "X protocol\|Xlib" | tail -1)
    echo "  boot poll $i: ${r:-no answer}"
    [ -n "$r" ] && [ "$r" != "loading" ] && break
    sleep 10
done
case "${r:-}" in
    ""|loading) echo "FATAL: NovaTerm never reached its main menu" >&2; exit 1;;
esac

# Drop out of warp, and PROVE it (see vicewarp.py -- a blind Alt+W is a toggle
# that fails silently in both directions).
DISPLAY=:0 timeout 90 python3 vicewarp.py 2>&1 | grep -v "X protocol\|Xlib" || {
    echo "FATAL: could not put VICE back to real speed" >&2; exit 1; }
echo "ready on the $LINK link"
