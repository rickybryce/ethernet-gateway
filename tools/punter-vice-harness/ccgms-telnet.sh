#!/usr/bin/env bash
# CCGMS 2021 over the TELNET link, for the XMODEM and Punter pair.
#
#   VICE x64sc (CCGMS, SwiftLink ACIA $DE00)
#        |  ip232 on TCP 25232
#      tcpser (virtual Hayes modem)
#        |  telnet TCP 2323
#   ethernetgateway
#
# Why this rig exists when CCGMS already passed 4/4 on serial: Punter C1
# blocks are dense with 0xFF and 0x0D, and telnet is the only link where those
# have to survive IAC escaping.  Serial has no IAC layer at all, so the serial
# run cannot exercise it -- and that layer is where the RFC 856 defect lived
# (`8b6c51d`, BINARY refused while already sending binary, which hit every
# binary protocol over telnet).
#
# **tcpser must be up BEFORE VICE.**  VICE's ip232 side is a client that
# connects once and never retries, so starting them the other way round, or
# restarting tcpser under a live emulator, strands it -- and that presents as
# a hang worse than whatever was being fixed.
#
# **The disk is a PRISTINE copy with the payload written on, and nothing
# else.**  Stripping the unrelated programs off it with `c1541 -delete` and
# `-validate` to free space broke CCGMS's boot outright -- a black screen with
# the drive light on.  53 blocks free is plenty: the payload is 7 and each
# download is 8.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
BIN="${GATEWAY_BIN:-$REPO_ROOT/target/release/ethernetgateway}"
CCGMS_D64="${CCGMS_D64:-$HOME/Desktop/ccgms-2021/ccgms 2021.d64}"

[ -x "$BIN" ]       || { echo "FATAL: no gateway binary at $BIN" >&2; exit 1; }
[ -f "$CCGMS_D64" ] || { echo "FATAL: no CCGMS disk at $CCGMS_D64" >&2; exit 1; }

ours() {
    local name="$1" p d
    for p in $(pgrep -x "$name" 2>/dev/null); do
        d=$(readlink /proc/$p/cwd 2>/dev/null)
        case "$d" in *punter-vice-harness*) echo "$p";; esac
    done
}
for name in x64sc ethernetgateway socat tcpser; do
    for p in $(ours "$name"); do kill "$p" 2>/dev/null; done
done
pkill -f "socat.*ttyGW" 2>/dev/null
# Wait for them to be GONE.  The gateway holds the data directory's lock until
# its graceful shutdown finishes (~5 s) and the replacement then refuses to
# start, naming a pid that is on its way out.
for _ in $(seq 1 200); do
    [ -z "$(ours ethernetgateway)$(ours x64sc)$(ours tcpser)" ] \
        && ! pgrep -f "socat.*ttyGW" >/dev/null 2>&1 && break
    sleep 0.1
done
[ -n "$(ours ethernetgateway)" ] && { echo "FATAL: previous gateway will not exit" >&2; exit 1; }

mkdir -p run
cp -f "$CCGMS_D64" run/ccgms-work.d64
c1541 -attach run/ccgms-work.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1

DATA="$HERE/run/ethernetgateway-data"
mkdir -p "$DATA/transfer"
[ -f "$DATA/egateway.conf" ] || cp "$HERE/egateway.harness.conf" "$DATA/egateway.conf"
find "$DATA/transfer" -maxdepth 1 -type f \
    ! -name 'EGT8080.COM' ! -name 'EGT80.COM' -delete
cp -f payloads/* "$DATA/transfer/" 2>/dev/null
# Telnet link: the serial port is not used, and leaving it on would have the
# gateway holding a PTY that no longer exists.
sed -i 's/^serial_a_enabled = .*/serial_a_enabled = false/' "$DATA/egateway.conf"
rm -f run/ttyGW run/ttyC64

GATEWAY_BIN="$BIN" nohup ./start-gateway.sh >/dev/null 2>&1 &
sleep 6
pgrep -x ethernetgateway >/dev/null || { echo "FATAL: gateway did not start" >&2; exit 1; }
grep "Telnet server listening" gateway.log | tail -1

TCPSER="${TCPSER:-$HOME/claude/punter-vice/tcpser/tcpser}" nohup ./start-tcpser.sh > tcpser.log 2>&1 &
for _ in $(seq 1 50); do ss -ltn 2>/dev/null | grep -q 25232 && break; sleep 0.2; done
ss -ltn 2>/dev/null | grep -q 25232 || { echo "FATAL: tcpser not listening on 25232; see tcpser.log" >&2; exit 1; }
echo "tcpser listening on 25232 -> telnet 127.0.0.1:2323"

# `-remotemonitor` is not optional even for a hand-driven run: it is the only
# way anything here can READ the screen.  Left off twice, and both times a
# blind probe was mistaken for a rig that had not come up.
DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    -rsdev1 "127.0.0.1:25232" -rsdev1ip232 -rsdev1baud 2400 \
    -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -autostart run/ccgms-work.d64 > /tmp/vice-ccgms-telnet.log 2>&1 &
sleep 30
pgrep -x x64sc >/dev/null || { echo "FATAL: VICE did not start" >&2; exit 1; }
echo "VICE up (started with -warp for the load -- press Alt+W to turn warp OFF before transferring)"
echo
echo "Download picker will list:"
python3 -c "
import os
d='$DATA/transfer'
for i,f in enumerate(sorted([f for f in os.listdir(d) if os.path.isfile(os.path.join(d,f))], key=str.lower),1):
    print('  %d  %s%s' % (i,f,'   <== PUNTEST.SEQ' if f=='PUNTEST.SEQ' else ''))"
