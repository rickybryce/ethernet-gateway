#!/usr/bin/env python3
"""Arm one NovaTerm receiver with NOTHING on the other end, and watch the wire.

    step-armonly.py <protocol-index> [save-name]

The wiretap says the C64 transmits nothing after Xmodem-CRC is armed.  That
accuses either NovaTerm or the path to it, and the gateway cannot be the
difference if it is never dialled.  So this arms the receiver with no call in
progress: whatever the module emits on its own -- a 'C', a NAK, nothing --
lands in socat's log with no second party to blame.

Run it once per index and compare: index 4 (Xmodem-1k) is the cell that PASSES
and index 3 (Xmodem-CRC) is the cell that fails, on the same disk, the same
dialogs and the same machine.
"""
import sys, time, novaterm

index = int(sys.argv[1]) if len(sys.argv) > 1 else 3
name  = sys.argv[2] if len(sys.argv) > 2 else 'armtest'

def dump(nt, tag):
    print("\n===== %s  (%s)" % (tag, time.strftime("%H:%M:%S")), flush=True)
    for l in nt.text():
        if l.strip():
            print("|%s|" % l, flush=True)

nt = novaterm.NovaTerm()
nt.ensure_terminal_mode()

nt.keys.focus(); nt.keys.combo('Tab', 'p'); time.sleep(8.0)
for _ in range(index):
    nt.press('Down', 0.35)
nt.press('Return', 3.0); time.sleep(10.0)
dump(nt, "protocol index %d selected" % index)

nt.keys.focus(); nt.keys.combo('Tab', 'd'); time.sleep(4.0)
dump(nt, "C= D (receiver dialog)")

if any('.ile:' in l or 'ile:' in l for l in nt.text()):
    nt.type(name + '\n', 2.0); dump(nt, "save-as name")

for _ in range(3):
    scr = nt.text()
    if any('prg' in l for l in scr):
        nt.type('s\n', 1.2); dump(nt, "file type -> s")
    elif any('eplace' in l for l in scr):
        nt.type('y', 1.2); dump(nt, "replace -> y")
    else:
        break

print("\n***** ARMED at %s -- watching the wire for 45s" % time.strftime("%H:%M:%S"),
      flush=True)
for i in range(9):
    time.sleep(5)
    dump(nt, "armed +%ds" % ((i + 1) * 5))
