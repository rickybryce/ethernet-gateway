#!/usr/bin/env bash
# Bring up the SERIAL rig for a HAND-DRIVEN transfer matrix.
#
#   VICE x64sc (NovaTerm, SwiftLink ACIA $DE00)
#        |  run/ttyC64
#      socat PTY pair (raw)
#        |  run/ttyGW
#   ethernetgateway, serial port A in modem mode
#
# There is no tcpser on this link: the C64 dials our OWN modem emulator, which
# resolves `ethernetgateway` itself.  tcpser is the telnet rig only.
#
# **Why a separate script from one-run.sh.**  That one drives the transfer
# too, and the harness either answers the post-transfer prompt or outlives it,
# so it is structurally blind to everything after the last data byte -- which
# is where four of this project's defects were found.  This brings the rig up
# and then gets out of the way.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
BIN="${GATEWAY_BIN:-$REPO_ROOT/target/release/ethernetgateway}"

[ -x "$BIN" ] || { echo "FATAL: no gateway binary at $BIN" >&2; exit 1; }

# Scope every kill to this harness's own processes by working directory -- a
# bare pkill would take out a VICE or a gateway the developer has open for
# something else.
ours() { # name -> pids whose cwd is inside this harness
    local name="$1" p d
    for p in $(pgrep -x "$name" 2>/dev/null); do
        d=$(readlink /proc/$p/cwd 2>/dev/null)
        case "$d" in *punter-vice-harness*) echo "$p";; esac
    done
}
for name in x64sc ethernetgateway socat; do
    for p in $(ours "$name"); do kill "$p" 2>/dev/null; done
done
pkill -f "socat.*ttyGW" 2>/dev/null

# **Wait for them to be gone; do not sleep a guess.**  Both of the processes
# here take longer to die than the obvious `sleep 2`, and both failures look
# like something else entirely:
#
#   * the gateway shuts down gracefully -- goodbye broadcast, a 3 s serial
#     join, a 2 s runtime drop -- and until it exits it still holds the data
#     directory's lock, so the replacement refuses to start with "another copy
#     holds the ports" and names a pid that is on its way out.
#   * socat REMOVES its link= symlinks on the way out, so a pair made before
#     the old process has died is unlinked by the corpse, and the run fails
#     later with a serial link that simply does not carry.
for _ in $(seq 1 200); do
    [ -z "$(ours ethernetgateway)$(ours x64sc)" ] \
        && ! pgrep -f "socat.*ttyGW" >/dev/null 2>&1 && break
    sleep 0.1
done
if [ -n "$(ours ethernetgateway)" ]; then
    echo "FATAL: the previous gateway ($(ours ethernetgateway)) will not exit" >&2
    exit 1
fi

# A fresh transfer disk: NovaTerm asks "Replace?" otherwise, and that question
# is asked inside the gateway's 45-second negotiation window.
mkdir -p run
c1541 -format "xfer,01" d64 run/xfer.d64 >/dev/null 2>&1
c1541 -attach run/xfer.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1

# Clean slate in the transfer dir, then re-seed.  Uploads land in the very
# directory the download picker lists, so leftovers shift PUNTEST.SEQ's menu
# number out from under the chart (measured: it drifted from #4 to #8).
DATA="$HERE/run/ethernetgateway-data"
mkdir -p "$DATA/transfer"
[ -f "$DATA/egateway.conf" ] || cp "$HERE/egateway.harness.conf" "$DATA/egateway.conf"
find "$DATA/transfer" -maxdepth 1 -type f \
    ! -name 'EGT8080.COM' ! -name 'EGT80.COM' -delete
cp -f payloads/* "$DATA/transfer/" 2>/dev/null
sed -i 's/^serial_a_enabled = .*/serial_a_enabled = true/' "$DATA/egateway.conf"

# The wire.  `raw` is not optional: a cooked line discipline maps CR to LF and
# would corrupt every block of every protocol, identically on each retry, past
# any CRC.  It must exist before the gateway starts -- the gateway opens its
# serial port at launch and a missing port is not retried.
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
grep -q "Serial port A" gateway.log 2>/dev/null \
    && grep "Serial port A" gateway.log | tail -2

# -warp to get NovaTerm loaded quickly; toggled back off below so the transfer
# itself runs at the C64's real speed.
# `-remotemonitor` is not optional even for a hand-driven run: it is the only
# way anything here can READ the C64's screen (NovaTerm relocates its screen to
# $8C00 and scans the keyboard matrix itself, so the KERNAL is no help).
# Leaving it off makes every status check silently return nothing, which reads
# as "NovaTerm did not load" when it has loaded perfectly well.
DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    -rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400 \
    -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -drive10type 1541 -10 run/xfer.d64 \
    -autostart "$HOME/Documents/NovaTerm/novaterm_9.6c.d64" > /tmp/vice.log 2>&1 &

echo "Waiting for NovaTerm to load..."
for i in $(seq 1 12); do
    sleep 10
    r=$(DISPLAY=:0 timeout 40 python3 -c "
import novaterm
nt=novaterm.NovaTerm(); s=nt.selected()
print(novaterm.MAIN_ITEMS[s] if s is not None else 'loading')" 2>/dev/null \
        | grep -v "X protocol\|Xlib" | tail -1)
    [ -n "$r" ] && [ "$r" != loading ] && { echo "NovaTerm up (menu: $r)"; break; }
done
# Warp off, so the transfer runs at the machine's real speed.
DISPLAY=:0 timeout 60 python3 -c "
import novaterm,time; nt=novaterm.NovaTerm(); nt.keys.focus()
nt.keys.combo('Alt_L','w'); time.sleep(2)" 2>/dev/null >/dev/null

echo
echo "Rig up.  Download picker will list, in order:"
ls "$DATA/transfer" | sort -f | nl -w3 -s'  '
