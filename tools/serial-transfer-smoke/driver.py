#!/usr/bin/env python3
"""Transfers to and from the gateway over a SERIAL link, through its own menu.

`tools/telnet-transfer-smoke` proves the product's transfer menu over telnet.
`tools/peer-transfer-smoke` proves the gateway as a *pipe* between two serial
ports.  Neither covers the gateway as an **endpoint over a serial link** --
dialling its own menu with `ATDT ethernetgateway` and transferring to it --
which is how a real vintage machine on a wire reaches it.

Everything but the transport is imported from the telnet driver on purpose.
Two harnesses that navigate the same menus in two copies of the same code
drift, and then a difference between the links reads as a gateway defect.

    ./run.sh                 # every protocol, both directions
    ./run.sh zmodem          # one protocol
    SIZE=32768 ./run.sh      # a bigger payload

The telnet control is the sibling harness, `tools/telnet-transfer-smoke`,
which this one imports -- run both and any difference is the link.
"""
import os, sys, time, subprocess, filecmp, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "telnet-transfer-smoke"))

import driver as T          # the telnet harness: menus, settle(), handoff()
from link import PtyLink


class SerialSession(T.Session):
    """The telnet Session with the socket swapped for a PTY.

    Telnet's IAC handling is inherited and simply never fires: a serial wire
    carries no options, so `0xFF` is data.  That is also why the IAC-escaping
    toggle matters less here -- the gateway does not escape on a serial link --
    but `to_menu` still checks and presses `I`, because being wrong about that
    is a corrupt file rather than a slow one.
    """

    def __init__(self, dev):
        self.s = PtyLink(dev)
        self.s.settimeout(0.4)
        self.buf = b""
        self.log = b""


def dial(dev, tries=3):
    """Reach the gateway's own menu from its modem emulator.

    `ATDT ethernetgateway` is the modem's name for this gateway's menu -- the
    same target the VICE/NovaTerm harness dials for its serial runs.
    """
    for attempt in range(1, tries + 1):
        s = SerialSession(dev)
        # A previous run leaves the modem ONLINE, and a PTY pair does not drop
        # carrier the way unplugging a cable would -- socat holds both ends
        # open.  So every dial begins by getting back to command mode the way
        # a person would: the `+++` escape needs a guard time of silence on
        # either side of it (S12), or the modem reads it as three data bytes.
        s.drain(0.5)
        time.sleep(1.2)
        s.send("+++")
        time.sleep(1.2)
        s.clear(); s.send("ATH\r"); s.drain(1.0)
        s.clear(); s.send("ATZ\r"); s.drain(1.0)
        if b"OK" not in s.buf:
            s.clear(); s.send("ATZ\r"); s.drain(1.5)
        s.clear(); s.send("ATDT ethernetgateway\r")
        if s.wait(b"CONNECT", timeout=15):
            if s.wait(b"BACKSPACE", timeout=20):
                s.send(b"\x08")                 # 0x08 -> ANSI
                s.wait(b"color", timeout=10)
                s.send(b"N")                    # plain text: easy to match
                s.drain(2.0)
                return s
            raise SystemExit("connected but no terminal detection:\n"
                             + s.text()[-800:])
        print(f"  dial attempt {attempt} got no CONNECT", flush=True)
        s.close()
        time.sleep(2)
    raise SystemExit("could not dial the gateway over the serial link")


def main():
    dev   = os.environ.get("SERIAL_DEV")
    xfer  = os.environ.get("XFER_DIR")
    work  = os.environ.get("WORK_DIR")
    only  = sys.argv[1] if len(sys.argv) > 1 else None
    size  = int(os.environ.get("SIZE", "8192"))
    if not (dev and xfer and work):
        raise SystemExit("SERIAL_DEV, XFER_DIR and WORK_DIR must be set (use ./run.sh)")

    # Substitute the transport and reuse the telnet harness's menu code
    # unchanged.  Reaching in like this is deliberate: the alternative is a
    # second copy of the navigation, and the whole value of running both links
    # is that only the transport differs.
    T.login = lambda host=None, port=None: dial(dev)

    payload = os.path.join(work, "payload.bin")
    if not os.path.exists(payload):
        raise SystemExit(f"missing payload {payload}")
    # The gateway sends from its own transfer dir, so the download source has
    # to be there under the name the picker will list.
    shutil.copyfile(payload, os.path.join(xfer, "payload.bin"))

    # XMODEM-1K has no upload menu key of its own: the gateway's receiver
    # detects STX per block, so 1K is the *sender's* choice and the menu entry
    # is plain `X`.  The telnet harness leaves that path untested; `sx -k` is
    # what actually exercises it.
    T.UPLOAD_KEY["xmodem-1k"] = "X"
    T.UPLOAD_SEND["xmodem-1k"] = ["sx", "-k"]

    protos = ["xmodem", "xmodem-1k", "ymodem", "zmodem"]
    if only:
        if only not in protos:
            raise SystemExit(f"unknown protocol {only!r}; have {protos}")
        protos = [only]

    print(f"serial link: {dev}   payload: {size} bytes", flush=True)
    for p in protos:
        print(f"--- {p} download (gateway -> us)", flush=True)
        try:
            T.download(None, None, p, os.path.join(xfer, "payload.bin"),
                       os.path.join(work, "out"))
        except Exception as e:
            T.bad(f"download/{p}: {type(e).__name__}: {e}")
        if p in T.UPLOAD_KEY:
            print(f"--- {p} upload (us -> gateway)", flush=True)
            try:
                T.upload(None, None, p, payload, xfer)
            except Exception as e:
                T.bad(f"upload/{p}: {type(e).__name__}: {e}")

    print(f"\n{T.PASS} passed, {T.FAIL} failed", flush=True)
    return 1 if T.FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
