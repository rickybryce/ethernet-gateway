#!/usr/bin/env python3
"""Dial through the slave and walk to a screen, printing what the far end sends.
    ptymenu.py <dial> <keys...>   e.g. ptymenu.py ethernetgateway 08 n f
Each arg after the dial is either two hex digits (a raw byte) or literal text.
"""
import os, sys, time, tty
dev = "/home/ricky/relay-vice/run/ttyC64"
fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK); tty.setraw(fd)
def rd(t):
    out=b""; end=time.time()+t
    while time.time()<end:
        try:
            d=os.read(fd,4096)
            if d: out+=d
        except BlockingIOError: time.sleep(0.05)
    return out
def show(tag,b):
    print("==== %s ===="%tag)
    print("".join(chr(x) if 32<=x<127 or x in (10,13) else ("\n" if x==13 else ".") for x in b))
os.write(fd,b"+++"); time.sleep(1.5); rd(0.5)
os.write(fd,b"ATH\r"); time.sleep(1.0); rd(0.5)
os.write(fd,b"ATZ\r"); time.sleep(1.0); rd(0.5)
os.write(fd,("ATDT "+sys.argv[1]+"\r").encode())
show("dial", rd(12))
for a in sys.argv[2:]:
    if len(a)==2 and all(c in "0123456789abcdefABCDEF" for c in a):
        os.write(fd, bytes([int(a,16)]))
    else:
        os.write(fd, a.encode())
    show("after %r"%a, rd(6))
