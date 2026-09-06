#!/usr/bin/env bash
# The gateway as an ENDPOINT over a serial link: dial its own menu with
# ATDT ethernetgateway and transfer to and from it with real lrzsz.
#
# The link is a socat PTY pair -- the gateway opens one end as its serial
# port A in modem mode, the driver (or minicom) opens the other.  A PTY has
# no baud rate, so this runs at host speed rather than 2400, which is the
# whole reason it is quicker than driving a real terminal under emulation.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
WORK="$HERE/work"
DATA="$WORK/ethernetgateway-data"
XFER="$DATA/transfer"
GATEWAY_BIN="${GATEWAY_BIN:-$HERE/../../target/debug/ethernetgateway}"
SIZE="${SIZE:-8192}"
PORT="${PORT:-2398}"

[ -x "$GATEWAY_BIN" ] || { echo "no gateway binary at $GATEWAY_BIN (cargo build)"; exit 2; }
command -v socat >/dev/null || { echo "socat is required"; exit 2; }
command -v sx >/dev/null || { echo "lrzsz is required"; exit 2; }

cleanup() {
    for p in $(pgrep -x ethernetgateway 2>/dev/null); do
        case "$(readlink /proc/$p/cwd 2>/dev/null)" in
            *serial-transfer-smoke*) kill "$p" 2>/dev/null;;
        esac
    done
    [ -n "${SOCAT_PID:-}" ] && kill "$SOCAT_PID" 2>/dev/null
    return 0
}
trap cleanup EXIT
cleanup; sleep 1

rm -rf "$WORK"; mkdir -p "$XFER" "$WORK/out"

# A payload with every byte value and long runs of the bytes each protocol
# treats specially -- a transfer that only carries text proves nothing about
# framing.  Same reasoning as PUNTEST.SEQ in the VICE harness.
python3 - "$WORK/payload.bin" "$SIZE" <<'PY'
import sys, os
path, size = sys.argv[1], int(sys.argv[2])
body = bytearray()
for v in range(256):
    body += bytes([v]) * 4
for run in (0x18, 0x11, 0x13, 0x1A, 0x0D, 0x0A, 0x0C, 0x7F, 0x08, 0xFF):
    body += bytes([run]) * 24
while len(body) < size:
    body += bytes((i * 7 + len(body)) & 0xFF for i in range(64))
open(path, "wb").write(bytes(body[:size]))
PY

# The gateway opens the device at startup, so the pair must exist first.
socat -d -d "pty,raw,echo=0,link=$WORK/ttyGW" "pty,raw,echo=0,link=$WORK/ttyUS" \
    > "$WORK/socat.log" 2>&1 &
SOCAT_PID=$!
for _ in $(seq 1 40); do [ -e "$WORK/ttyGW" ] && [ -e "$WORK/ttyUS" ] && break; sleep 0.25; done
[ -e "$WORK/ttyGW" ] || { echo "socat did not create the pty pair"; cat "$WORK/socat.log"; exit 2; }

cat > "$DATA/egateway.conf" <<CONF
telnet_enabled = true
telnet_port = $PORT
security_enabled = false
transfer_dir = ethernetgateway-data/transfer
verbose = true
enable_console = false
ssh_enabled = false
webserver_enabled = false
serial_a_enabled = true
serial_a_port = $WORK/ttyGW
serial_a_mode = modem
serial_a_baud = 115200
CONF

( cd "$WORK" && "$GATEWAY_BIN" > "$WORK/gateway.log" 2>&1 & )
for _ in $(seq 1 60); do grep -q "Serial port A" "$WORK/gateway.log" 2>/dev/null && break; sleep 0.5; done
sleep 2

echo "=== gateway startup"
grep -iE "serial|telnet server|FATAL|error" "$WORK/gateway.log" | head -10

SERIAL_DEV="$WORK/ttyUS" XFER_DIR="$XFER" WORK_DIR="$WORK" SIZE="$SIZE" \
    python3 driver.py "$@"
rc=$?
echo "=== to drive this link by hand:  minicom -D $WORK/ttyUS -b 115200"
exit $rc
