#!/usr/bin/env python3
"""A PTY dressed as a socket, so one driver can serve both links.

`tools/telnet-transfer-smoke/driver.py` reaches its transport through a very
small surface -- recv / sendall / settimeout / setblocking / fileno / close --
so a serial link needs a shim of that shape rather than a second driver.  The
menu navigation, the IAC toggle, the `settle()` rule and the lrzsz handoff are
then literally the same code, which is the point: a difference in the *result*
between the two links is then a difference in the *gateway*, not in two
harnesses that drifted apart.

The PTY is put in raw mode explicitly.  A cooked line discipline maps CR to LF
on the way through and would corrupt every block of every protocol -- and it
would do it identically on each retry, so no CRC could recover it.
"""
import os, termios, tty, select, socket


class PtyLink:
    def __init__(self, dev):
        self.fd = os.open(dev, os.O_RDWR | os.O_NOCTTY)
        tty.setraw(self.fd)
        a = termios.tcgetattr(self.fd)
        a[0] = 0                      # iflag: no CR/NL mapping, no flow control
        a[1] = 0                      # oflag: no output post-processing
        a[3] = 0                      # lflag: no echo, no canonical mode
        a[6][termios.VMIN] = 0
        a[6][termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        self._timeout = 0.4

    # -- the socket surface the driver uses -------------------------------
    def settimeout(self, t):
        self._timeout = t

    def setblocking(self, flag):
        self._timeout = None if flag else 0.0

    def fileno(self):
        return self.fd

    def recv(self, n):
        t = self._timeout
        r, _, _ = select.select([self.fd], [], [], t)
        if not r:
            raise socket.timeout()
        try:
            d = os.read(self.fd, n)
        except OSError:
            raise EOFError("pty closed")
        # A PTY with no writer reads EOF; on a serial link that is "quiet",
        # not "closed", so report it as a timeout or the driver gives up the
        # moment the gateway pauses between prompts.
        if not d:
            raise socket.timeout()
        return d

    def sendall(self, d):
        while d:
            n = os.write(self.fd, d)
            d = d[n:]

    def close(self):
        try:
            os.close(self.fd)
        except Exception:
            pass
