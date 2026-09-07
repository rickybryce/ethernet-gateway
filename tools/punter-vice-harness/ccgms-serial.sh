#!/usr/bin/env bash
# Bring up the SERIAL rig with CCGMS 2021 as the terminal, for hand-driven
# XMODEM and Punter checks against a SECOND independent implementation.
#
#   VICE x64sc (CCGMS 2021 from cartridge, SwiftLink ACIA $DE00)
#        |  run/ttyC64
#      socat PTY pair (raw)
#        |  run/ttyGW
#   ethernetgateway, serial port A in modem mode
#
# **CCGMS boots from its own DISK, and the payload is written onto that same
# disk, so drive 8 is program and transfer medium at once.**  Two routes were
# tried first and both cost time:
#
#   * The bundled `.crt` is an **EasyFlash** cartridge (CRT hardware type 32,
#     not a plain ROM), so `-cartcrt` attaches it and nothing boots -- the
#     screen just sits at BASIC.  EasyFlash needs its own handling and a
#     jumper, which is more moving parts than this test is worth.
#   * Booting CCGMS from drive 8 and putting `xfer.d64` on 9 or 10 means
#     telling CCGMS which device to use, and its device selector is
#     EasyFlash-only ("CFG DEVICE" in the F7 menu), so on the disk build the
#     device is effectively 8.
#
# Writing `PUNTEST.SEQ` onto a working COPY of the CCGMS disk dissolves the
# question: 53 blocks are free after CCGMS's own files, the payload is 7.
# Why CCGMS at all when NovaTerm already passed 24/24: it is a different
# implementation by a different author, and Punter C1 is the protocol CCGMS
# defined.  Two terminals agreeing is evidence; one terminal agreeing with
# itself is not.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
BIN="${GATEWAY_BIN:-$REPO_ROOT/target/release/ethernetgateway}"
CCGMS_D64="${CCGMS_D64:-$HOME/Desktop/ccgms-2021/ccgms 2021.d64}"

[ -x "$BIN" ]        || { echo "FATAL: no gateway binary at $BIN" >&2; exit 1; }
[ -f "$CCGMS_D64" ]  || { echo "FATAL: no CCGMS disk at $CCGMS_D64" >&2; exit 1; }

ours() { # name -> pids whose cwd is inside this harness
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
# Wait for them to be GONE, never sleep a guess: the gateway holds the data
# directory's lock until it has finished its graceful shutdown (~5 s), and
# socat unlinks its own symlinks on the way out.
for _ in $(seq 1 200); do
    [ -z "$(ours ethernetgateway)$(ours x64sc)$(ours tcpser)" ] \
        && ! pgrep -f "socat.*ttyGW" >/dev/null 2>&1 && break
    sleep 0.1
done
[ -n "$(ours ethernetgateway)" ] && { echo "FATAL: previous gateway will not exit" >&2; exit 1; }

mkdir -p run
# A fresh working copy of the CCGMS disk with the payload written onto it.
cp -f "$CCGMS_D64" run/ccgms-work.d64
c1541 -attach run/ccgms-work.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1

DATA="$HERE/run/ethernetgateway-data"
mkdir -p "$DATA/transfer"
[ -f "$DATA/egateway.conf" ] || cp "$HERE/egateway.harness.conf" "$DATA/egateway.conf"
find "$DATA/transfer" -maxdepth 1 -type f \
    ! -name 'EGT8080.COM' ! -name 'EGT80.COM' -delete
cp -f payloads/* "$DATA/transfer/" 2>/dev/null
sed -i 's/^serial_a_enabled = .*/serial_a_enabled = true/' "$DATA/egateway.conf"

# The wire.  `raw` matters: a cooked discipline maps CR to LF and would corrupt
# every block of every protocol, identically on each retry, past any CRC.
rm -f run/ttyGW run/ttyC64
socat pty,raw,echo=0,link="$HERE/run/ttyGW" \
      pty,raw,echo=0,link="$HERE/run/ttyC64" > socat.log 2>&1 &
for _ in $(seq 1 50); do
    [ -e run/ttyGW ] && [ -e run/ttyC64 ] && break
    sleep 0.1
done
[ -e run/ttyGW ] && [ -e run/ttyC64 ] || {
    echo "FATAL: socat did not create the PTY pair; see socat.log" >&2; exit 1; }

GATEWAY_BIN="$BIN" nohup ./start-gateway.sh >/dev/null 2>&1 &
sleep 6
pgrep -x ethernetgateway >/dev/null || { echo "FATAL: gateway did not start" >&2; exit 1; }
grep "Serial modem (Port A)" gateway.log | tail -1

# No readiness probe here: `novaterm.py` reads NovaTerm's own menu out of
# memory and knows nothing about CCGMS, so gating on it would block a rig that
# is actually up -- which is exactly what it did once already.  The cartridge
# boots in about two seconds; hand it over and let the operator look.
DISPLAY=:0 nohup x64sc -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    -rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400 \
    -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -autostart run/ccgms-work.d64 \
    > /tmp/vice-ccgms.log 2>&1 &

sleep 8
pgrep -x x64sc >/dev/null && echo "VICE up: CCGMS from disk on drive 8 (payload PUNTEST is on that same disk)" \
                          || { echo "FATAL: VICE did not start; see /tmp/vice-ccgms.log" >&2; exit 1; }
echo
echo "Download picker will list:"
python3 -c "
import os
d='$DATA/transfer'
for i,f in enumerate(sorted([f for f in os.listdir(d) if os.path.isfile(os.path.join(d,f))], key=str.lower),1):
    print('  %d  %s' % (i,f))"
