import socket, time, re, sys

class Mon:
    """VICE 3.7 text remote monitor. Entering it PAUSES the emulator; `x` resumes."""
    def __init__(self, port=29876):
        self.k = socket.create_connection(("127.0.0.1", port), 5)
        self.k.settimeout(1.5)
        self.drain(0.6)
    def drain(self, secs=0.5):
        """Read whatever is already waiting, for at most `secs`.

        **Poll in small slices rather than blocking on the socket timeout.**
        The socket is set to 1.5 s, so a drain of an EMPTY socket -- which is
        the normal case, since draining is a precaution against a stale prompt
        -- blocked the full 1.5 s however small a window the caller asked for.
        `cells()` drains five times (connect, three peeks, resume), so one
        screen read cost 5 x 1.5 = 7.5 s; measured at 7.54 s.

        That is not merely slow.  Entering the monitor PAUSES the emulated
        machine, so those seconds are stolen from the C64 while the gateway's
        45-second negotiation window runs on the wall clock: measured, the
        session clock advanced 0 s across 52.8 s of reading.  A download whose
        dialogs need five reads therefore armed its receiver ~78 s after the
        gateway said "start within 45 seconds", and the transfer failed --
        looking exactly like an XMODEM defect, in an instrument that was
        spending the budget of the thing it was measuring.
        """
        out = b""; end = time.time() + secs
        old = self.k.gettimeout()
        try:
            while True:
                left = end - time.time()
                if left <= 0:
                    break
                self.k.settimeout(min(left, 0.05))
                try: d = self.k.recv(65536)
                except socket.timeout: continue
                if not d: break
                out += d
        finally:
            self.k.settimeout(old)
        return out
    def cmd(self, c, wait=0.6):
        """Send a command and read until the monitor prompt comes back.

        Draining for a fixed time silently truncates a long dump -- a 1000-byte
        `m` is 63 lines and does not fit a fixed window -- and the loss shows up
        as a short read rather than as an error, which is the wrong failure to
        debug.  The prompt is the real end marker.
        """
        # Clear anything already waiting first.  The monitor leaves a prompt
        # behind after every exchange, and that STALE prompt satisfies the
        # end-of-reply test below the instant the command is sent -- so the
        # first command of a session returned ten bytes of prompt and none of
        # its own output, and the caller saw an empty parse rather than an
        # error.
        self.drain(0.15)
        self.k.sendall((c + "\n").encode())
        out = b""
        end = time.time() + max(wait, 8.0)
        while time.time() < end:
            try:
                d = self.k.recv(65536)
            except socket.timeout:
                if out.rstrip().endswith(b")"):
                    break
                continue
            if not d:
                break
            out += d
            if re.search(rb"\(C:\$[0-9a-f]{4}\)\s*$", out):
                break
        return out
    def peek(self, addr, n):
        """n bytes from addr, as a list of ints.

        Reads until it HAS the bytes rather than until a prompt appears.  The
        monitor leaves a prompt behind after every exchange, so any
        prompt-terminated read can be satisfied by the previous one and return
        nothing -- which shows up as an empty parse, not an error.  Asking for
        a known quantity and waiting for it has no such ambiguity.
        """
        self.drain(0.15)
        self.k.sendall(("m %04x %04x\n" % (addr, addr + n - 1)).encode())
        out = b""
        end = time.time() + 10.0
        while time.time() < end:
            try:
                d = self.k.recv(65536)
            except socket.timeout:
                if len(self._parse(out)) >= n:
                    break
                continue
            if not d:
                break
            out += d
            if len(self._parse(out)) >= n:
                break
        # Each line is `>C:0400  00 01 .. 0f   ................` -- take exactly
        # sixteen bytes after the address.  The trailing ASCII column can itself
        # look like hex ("abcdef01"), which a greedy run happily absorbed: the
        # first parser lost 28 of 1000 bytes that way and reported a short read
        # rather than wrong data, which is the only reason it was noticed.
        return self._parse(out)[:n]

    def _parse(self, out):
        by_addr = {}
        for line in out.decode("latin1").splitlines():
            # A line can carry the previous exchange's prompt in front of its
            # data -- `(C:$f140) >C:0400  00 01 ...` -- and that prompt looks
            # enough like an address to derail the match, which silently lost
            # the first sixteen bytes of every dump.
            line = re.sub(r"^\(C:\$[0-9a-f]{4}\)\s*", "", line.strip(), flags=re.I)
            m = re.match(r"^[>\s]*C:\$?([0-9a-f]{4})\s+(.*)$", line, re.I)
            if not m:
                continue
            toks = re.findall(r"\b[0-9a-f]{2}\b", m.group(2), re.I)[:16]
            by_addr[int(m.group(1), 16)] = [int(t, 16) for t in toks]
        vals = []
        for a in sorted(by_addr):
            vals += by_addr[a]
        return vals
    def screen_base(self):
        """Where the VIC-II is actually fetching characters from.

        **Not `$0400`.**  NovaTerm relocates its screen -- measured at `$8C00`,
        VIC bank `$8000` -- so a reader that assumes the default reports a
        screenful of stale memory and looks like a decode bug.  The registers
        know: `$D018` bits 7-4 give the offset in 1 KB units and CIA2 `$DD00`
        bits 0-1 select the 16 KB bank, inverted.
        """
        d018 = self.peek(0xD018, 1)[0]
        dd00 = self.peek(0xDD00, 1)[0]
        return (3 - (dd00 & 3)) * 0x4000 + ((d018 >> 4) & 0x0F) * 0x0400

    def screen(self, base=None):
        """The 40x25 text screen, decoded from screen codes."""
        v = self.peek(base if base is not None else self.screen_base(), 1000)
        if len(v) < 1000: return ["<short read: %d>" % len(v)]
        def ch(c):
            c &= 0x7F
            if c == 0x20 or c == 0x60: return ' '
            if 0x01 <= c <= 0x1A: return chr(ord('a') + c - 1)
            if 0x30 <= c <= 0x39: return chr(c)
            if c == 0x2E: return '.'
            if c == 0x2D: return '-'
            if c == 0x3A: return ':'
            if c == 0x2F: return '/'
            if c == 0x28: return '('
            if c == 0x29: return ')'
            if c == 0x3D: return '='
            if c == 0x2C: return ','
            if c == 0x21: return '!'
            if c == 0x3F: return '?'
            if 0x21 <= c <= 0x3F: return chr(c)
            return '.'
        return ["".join(ch(v[r*40+c]) for c in range(40)).rstrip() for r in range(25)]
    def resume(self):
        self.k.sendall(b"x\n"); self.drain(0.3)

if __name__ == "__main__":
    m = Mon(int(sys.argv[1]) if len(sys.argv) > 1 else 29876)
    for line in m.screen(): print("|%s|" % line)
    m.resume()
