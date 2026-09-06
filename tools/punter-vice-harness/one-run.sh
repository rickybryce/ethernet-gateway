#!/usr/bin/env bash
# One protocol, one direction, from a guaranteed-clean start.
#
# NovaTerm keeps state across a run -- an aborted transfer leaves a dialog up,
# the menu remembers where it was, the protocol resets to Zmodem -- and every
# attempt to recover in-place cost more time than a restart does.  So each run
# gets a fresh emulator.
#
#   ./one-run.sh <protocol> <download|upload> [serial|telnet]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO="${1:?protocol}"; DIR="${2:?download|upload}"; LINK="${3:-telnet}"
cd "$HERE"

for p in $(pgrep -x x64sc); do kill "$p" 2>/dev/null; done
for p in $(pgrep -x ethernetgateway); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *punter-vice-harness*) kill "$p" 2>/dev/null;; esac
done
pkill -x tcpser 2>/dev/null
sleep 3

# A fresh transfer disk every time: NovaTerm asks "Replace?" otherwise, and
# that question is asked inside the gateway's 45-second window.
c1541 -format "xfer,01" d64 run/xfer.d64 >/dev/null 2>&1
c1541 -attach run/xfer.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1
rm -f run/ethernetgateway-data/transfer/*up.seq run/ethernetgateway-data/transfer/*up*.usr
# Refresh the payloads unconditionally.  start-gateway.sh seeds them only when
# absent, which is right for a long-lived rig and wrong for a test: changing
# payloads/PUNTEST.SEQ then had no effect, and an experiment that varied the
# input silently ran against the old one.
cp -f payloads/* run/ethernetgateway-data/transfer/ 2>/dev/null

if [ "$LINK" = serial ]; then
    sed -i 's/^serial_a_enabled = .*/serial_a_enabled = true/' run/ethernetgateway-data/egateway.conf
    RS=(-rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400); DIALNO=ethernetgateway
else
    sed -i 's/^serial_a_enabled = .*/serial_a_enabled = false/' run/ethernetgateway-data/egateway.conf
    RS=(-rsdev1 "127.0.0.1:25232" -rsdev1ip232 -rsdev1baud 2400); DIALNO=1
fi

# NOT `> gateway.log`: start-gateway.sh already tees to that file, and two
# writers both starting at offset 0 interleave and overwrite each other.  It
# duplicated ACK lines and truncated others, which made three cleanly ACKed
# XMODEM blocks look like a sender restarting in a loop -- a defect that was
# never there.
GATEWAY_BIN=/home/ricky/xmodem/target/debug/ethernetgateway nohup ./start-gateway.sh >/dev/null 2>&1 &
sleep 6
[ "$LINK" = telnet ] && { nohup ./start-tcpser.sh > tcpser.log 2>&1 & sleep 3; }

DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    "${RS[@]}" -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -drive10type 1541 -10 run/xfer.d64 \
    -autostart "$HOME/Documents/NovaTerm/novaterm_9.6c.d64" > /tmp/vice.log 2>&1 &

sleep 30
for i in 1 2 3 4 5 6; do
    r=$(DISPLAY=:0 timeout 40 python3 -c "
import novaterm
nt=novaterm.NovaTerm(); s=nt.selected()
print(novaterm.MAIN_ITEMS[s] if s is not None else 'loading')" 2>/dev/null | grep -v "X protocol\|Xlib" | tail -1)
    [ "$r" != "loading" ] && break
    sleep 15
done
DISPLAY=:0 timeout 60 python3 -c "
import novaterm,time; nt=novaterm.NovaTerm(); nt.keys.focus(); nt.keys.combo('Alt_L','w'); time.sleep(2)" \
    2>/dev/null >/dev/null
DISPLAY=:0 timeout 560 python3 run-transfer.py "$PROTO" "$DIR" "$DIALNO" 2>&1 | grep -v "X protocol\|Xlib"
