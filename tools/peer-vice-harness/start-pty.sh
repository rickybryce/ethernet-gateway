#!/usr/bin/env bash
# A socat PTY pair for the peer-to-peer test: the gateway holds run/ttyGW,
# VICE holds run/ttyC64.  raw is not optional -- a cooked discipline maps CR to
# LF and would corrupt every block of every protocol, identically on each retry.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
pkill -f "socat.*peer-vice.*ttyGW" 2>/dev/null
for _ in $(seq 1 50); do pgrep -f "socat.*peer-vice.*ttyGW" >/dev/null 2>&1 || break; sleep 0.1; done
rm -f run/ttyGW run/ttyC64
socat pty,raw,echo=0,link="$HERE/run/ttyGW" pty,raw,echo=0,link="$HERE/run/ttyC64" > socat.log 2>&1 &
for _ in $(seq 1 50); do [ -e run/ttyGW ] && [ -e run/ttyC64 ] && break; sleep 0.1; done
[ -e run/ttyGW ] && [ -e run/ttyC64 ] && echo "PTY pair up: $HERE/run/ttyGW <-> $HERE/run/ttyC64" || { echo "FATAL: no PTY pair; see socat.log" >&2; exit 1; }
