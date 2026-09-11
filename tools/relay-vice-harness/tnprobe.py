#!/usr/bin/env python3
"""Walk a gateway's telnet menu from here, answering IAC, and show each screen.

    tnprobe.py <host> <port> <step> ...
A step is two hex digits (a raw byte) or literal text.  Used to work out the
Telnet Gateway's prompt sequence WITHOUT touching the emulator, so the rig can
keep running while the navigation is designed.
"""
import socket, sys, time

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

def negotiate(sock, data, out):
    """Answer option negotiation the dumb-but-correct way: refuse everything."""
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            c = data[i+1]
            if c in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                opt = data[i+2]
                if c == DO:    sock.sendall(bytes([IAC, WONT, opt]))
                elif c == WILL: sock.sendall(bytes([IAC, DONT, opt]))
                i += 3; continue
            if c == SB:
                j = data.find(bytes([IAC, SE]), i)
                i = (j + 2) if j >= 0 else len(data); continue
            if c == IAC:
                out.append(IAC); i += 2; continue
            i += 2; continue
        out.append(b); i += 1
    return out

def rd(sock, secs):
    out = bytearray(); end = time.time() + secs
    sock.settimeout(0.4)
    while time.time() < end:
        try:
            d = sock.recv(4096)
            if not d: break
            negotiate(sock, d, out)
        except socket.timeout:
            continue
    return bytes(out)

def show(tag, b):
    print("==== %s ====" % tag)
    txt = "".join(chr(x) if 32 <= x < 127 or x in (10, 13) else
                  ("\n" if x == 13 else ".") for x in b)
    print(txt)

def main():
    host, port = sys.argv[1], int(sys.argv[2])
    s = socket.create_connection((host, port), 10)
    show("connect", rd(s, 6))
    for a in sys.argv[3:]:
        if len(a) == 2 and all(c in "0123456789abcdefABCDEF" for c in a):
            s.sendall(bytes([int(a, 16)]))
        else:
            s.sendall(a.encode())
        show("after %r" % a, rd(s, 6))
    s.close()

if __name__ == "__main__":
    sys.exit(main())
