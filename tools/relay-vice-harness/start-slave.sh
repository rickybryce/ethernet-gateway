#!/usr/bin/env bash
# Start the SLAVE gateway on 141, with a socat PTY pair for serial port A.
#   ./start-slave.sh [serial|telnet]
# serial: port A enabled on run/ttyGW (the C64 gets run/ttyC64).
# telnet: port A disabled -- the device reaches a gateway over TCP instead.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
LINK="${1:-serial}"
BIN="$HOME/ethernetgateway/target/release/ethernetgateway"
DATA="$HERE/run/ethernetgateway-data"

# Stop a slave started from here (identified by cwd, never by a bare pkill).
for p in $(pgrep -x ethernetgateway); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *relay-vice*) kill "$p" 2>/dev/null;; esac
done
sleep 2

if [ "$LINK" = serial ]; then
    sed -i "s|^serial_a_enabled = .*|serial_a_enabled = true|" "$DATA/egateway.conf"
    # Wait for an old socat to DIE before making a new pair: socat removes its
    # link= symlinks on the way out, so an overlapping one unlinks the pair the
    # new process just made.
    pkill -f "socat.*relay-vice.*ttyGW" 2>/dev/null
    for _ in $(seq 1 50); do
        pgrep -f "socat.*relay-vice.*ttyGW" >/dev/null 2>&1 || break
        sleep 0.1
    done
    rm -f run/ttyGW run/ttyC64
    # raw is not optional: a cooked discipline maps CR to LF and would corrupt
    # every block of every protocol, identically on each retry, past any CRC.
    # With SOCAT_TRACE=1 the pair is wiretapped.  The sniffer has to sit HERE
    # and not at either end: the question a failing transfer asks is "did the
    # device transmit?", and neither party can answer it -- the gateway's own
    # byte logger is one of the two suspects, and NovaTerm cannot be asked at
    # all.  socat sees each direction separately and is not a party to either.
    # Off by default: -v on a 12-cell sweep writes a log nobody will read.
    TRACE=()
    [ "${SOCAT_TRACE:-0}" = 1 ] && TRACE=(-x -v -lf "$HERE/socat-trace.log")
    socat "${TRACE[@]}" pty,raw,echo=0,link="$HERE/run/ttyGW" \
          pty,raw,echo=0,link="$HERE/run/ttyC64" > socat.log 2>&1 &
    for _ in $(seq 1 50); do
        [ -e run/ttyGW ] && [ -e run/ttyC64 ] && break
        sleep 0.1
    done
    if [ ! -e run/ttyGW ] || [ ! -e run/ttyC64 ]; then
        echo "FATAL: socat did not create the PTY pair; see socat.log" >&2
        exit 1
    fi
else
    sed -i "s|^serial_a_enabled = .*|serial_a_enabled = false|" "$DATA/egateway.conf"
fi

cd "$HERE/run"
# exec so this script IS the gateway: the orchestrator kills that pid and the
# gateway really stops (a | tee pipeline would orphan it on :2323).
exec "$BIN" > >(tee "$HERE/slave.log") 2>&1
