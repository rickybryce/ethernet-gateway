#!/usr/bin/env python3
"""Dial the slave modem from a plain PTY and print what comes back.

A positive control for the relay that does not involve the emulator: if this
shows the MASTER's menu, the relay carries; if it does not, nothing the C64
does later can.
    ptydial.py <dial-string> [seconds] [keys-to-send-after-connect]
"""
import os, sys, time, termios, tty

dev = "/home/ricky/relay-vice/run/ttyC64"
dial = sys.argv[1] if len(sys.argv) > 1 else "ethernetgateway"
secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
after = sys.argv[3] if len(sys.argv) > 3 else ""

fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
tty.setraw(fd)
def rd(t):
    out = b""; end = time.time() + t
    while time.time() < end:
        try:
            d = os.read(fd, 4096)
            if d: out += d
        except BlockingIOError:
            time.sleep(0.05)
    return out

os.write(fd, b"+++"); time.sleep(1.5); rd(0.5)
os.write(fd, b"ATH\r"); time.sleep(1.0); rd(0.5)
os.write(fd, b"ATZ\r"); time.sleep(1.0); rd(0.5)
os.write(fd, ("ATDT " + dial + "\r").encode()); 
buf = rd(secs)
if after:
    for ch in after:
        os.write(fd, ch.encode()); time.sleep(1.5)
    buf += rd(6.0)
sys.stdout.write(repr(buf[:4000]) + "\n\n")
sys.stdout.write("---- decoded ----\n")
sys.stdout.write("".join(chr(b) if 32 <= b < 127 or b in (10,13) else "." for b in buf[:4000]))
