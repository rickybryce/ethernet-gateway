#!/usr/bin/env python3
"""Live driver for the peer-dial smoke test.

Drives the two "device" ends of the socat PTY pairs that `run.sh` wires to a
headless gateway's Port A and Port B, and exercises peer-dial end to end:

  modem   : Port A modem, Port B modem. A dials B, B rings, B answers (ATA),
            data flows both ways.  Also checks self-dial and NO ANSWER.
  console : Port A modem, Port B telnet-serial (console). A dials B, connects
            directly (no ring), data flows both ways.

Exit code 0 = all checks passed, 1 = a check failed.  Requires pyserial.
"""

import argparse
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial not found: pip install pyserial (or apt install python3-serial)")

PASS, FAIL = 0, 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  PASS  {msg}")


def bad(msg):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {msg}")


def drain(ser, secs=0.4):
    """Discard whatever is buffered (e.g. the startup OK)."""
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if ser.in_waiting:
            ser.read(ser.in_waiting)
        time.sleep(0.02)


def send(ser, line):
    ser.write((line + "\r").encode())
    ser.flush()


def expect(ser, token, timeout, label=None):
    """Read until `token` (str) appears, or timeout.  Returns True/False."""
    label = label or f"'{token}'"
    tb = token.encode()
    buf = bytearray()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if tb in buf:
                ok(f"saw {label}")
                return True
        else:
            time.sleep(0.03)
    printable = bytes(buf).decode("ascii", "replace").replace("\r", "\\r").replace("\n", "\\n")
    bad(f"timed out waiting for {label} (got: '{printable}')")
    return False


def expect_any(ser, tokens, timeout, label):
    """Read until any of `tokens` (list of str) appears, or timeout."""
    tbs = [t.encode() for t in tokens]
    buf = bytearray()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            for t, tb in zip(tokens, tbs):
                if tb in buf:
                    ok(f"{label}: saw '{t}'")
                    return True
        else:
            time.sleep(0.03)
    printable = bytes(buf).decode("ascii", "replace").replace("\r", "\\r").replace("\n", "\\n")
    bad(f"{label}: timed out (wanted one of {tokens}, got '{printable}')")
    return False


def expect_bytes(ser, needle: bytes, timeout, label):
    buf = bytearray()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        n = ser.in_waiting
        if n:
            buf += ser.read(n)
            if needle in buf:
                ok(f"{label}: received {needle!r}")
                return True
        else:
            time.sleep(0.03)
    bad(f"{label}: did not receive {needle!r} (got {bytes(buf)!r})")
    return False


def at_setup(ser):
    """Reset + echo off + verbose so responses parse cleanly."""
    drain(ser)
    send(ser, "ATZ")
    time.sleep(0.3)
    drain(ser)
    send(ser, "ATE0V1")
    time.sleep(0.3)
    drain(ser)


def scenario_modem(a, b):
    print("[scenario: modem <-> modem]")
    at_setup(a)
    at_setup(b)

    # 1. Self-dial is refused.
    send(a, "ATD A@127.0.0.1")
    expect(a, "NO CARRIER", 5, "self-dial -> NO CARRIER")
    drain(a)

    # 2. A dials B; B must ring, then answer with ATA; both CONNECT.
    send(a, "ATD B@127.0.0.1")
    if expect(b, "RING", 8, "B receives RING"):
        send(b, "ATA")
        got_b = expect(b, "CONNECT", 8, "B (answerer) CONNECT")
        got_a = expect(a, "CONNECT", 8, "A (caller) CONNECT")
        if got_a and got_b:
            time.sleep(0.3)
            drain(a); drain(b)
            # 3. Transparent data both ways.
            a.write(b"PING-FROM-A\n"); a.flush()
            expect_bytes(b, b"PING-FROM-A", 4, "A->B data")
            b.write(b"PONG-FROM-B\n"); b.flush()
            expect_bytes(a, b"PONG-FROM-B", 4, "B->A data")
            # 4. Hang up from A with +++ then ATH.  ATH returns OK (Hayes),
            #    and tearing the bridge down makes B see carrier loss.
            time.sleep(1.2)               # +++ guard time
            a.write(b"+++"); a.flush()
            time.sleep(1.2)
            expect(a, "OK", 4, "A: +++ escape -> OK")
            drain(a)
            send(a, "ATH")
            expect(a, "OK", 4, "A: ATH -> OK")
            expect(b, "NO CARRIER", 5, "B: peer hung up -> NO CARRIER")

    # 5. NO ANSWER: B set to no auto-answer (S0=0) and nobody answers.
    at_setup(a); at_setup(b)
    send(b, "ATS0=0")
    time.sleep(0.2); drain(b)
    send(a, "ATS7=4")                     # short caller wait so the test is quick
    time.sleep(0.2); drain(a)
    send(a, "ATD B@127.0.0.1")
    # Let B ring but never answer; caller gives up after ~S7 seconds.
    # At the default ATX4 this is "NO ANSWER"; lower X degrades to "NO CARRIER".
    expect_any(a, ["NO ANSWER", "NO CARRIER"], 12, "A: unanswered call")
    # (B is still ringing; drain and reset so the port is idle again.)
    time.sleep(0.5); drain(b)


def scenario_console(a, b):
    print("[scenario: modem -> console]")
    at_setup(a)
    drain(b)                              # B is a raw console device (no AT)

    # A dials the console port; it connects directly (no ring).
    send(a, "ATD B@127.0.0.1")
    if expect(a, "CONNECT", 8, "A: console target CONNECT (no ring)"):
        time.sleep(0.3); drain(a)
        a.write(b"HELLO-CONSOLE\n"); a.flush()
        expect_bytes(b, b"HELLO-CONSOLE", 4, "A->console data")
        b.write(b"CONSOLE-REPLY\n"); b.flush()
        expect_bytes(a, b"CONSOLE-REPLY", 4, "console->A data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["modem", "console"], default="modem")
    ap.add_argument("--dev-a", required=True)
    ap.add_argument("--dev-b", required=True)
    ap.add_argument("--baud", type=int, default=9600)
    args = ap.parse_args()

    a = serial.Serial(args.dev_a, args.baud, timeout=0)
    b = serial.Serial(args.dev_b, args.baud, timeout=0)
    # Assert DTR/RTS so the ports look "live".
    for s in (a, b):
        try:
            s.dtr = True
            s.rts = True
        except Exception:
            pass

    try:
        if args.mode == "modem":
            scenario_modem(a, b)
        else:
            scenario_console(a, b)
    finally:
        a.close()
        b.close()

    print(f"\n{PASS} passed, {FAIL} failed.")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
