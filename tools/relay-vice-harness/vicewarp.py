#!/usr/bin/env python3
"""Leave VICE running at REAL speed, and prove it rather than assume it.

The rig boots NovaTerm under `-warp` because the boot is dead time, then has to
drop back to 1x for the transfers: the gateway's timeouts are wall-clock, and
the validated matrix was measured at 1x.

Alt+W is a **toggle**, and the old harness pressed it blindly.  A blind toggle
has two failure modes and neither announces itself: pressed when the keyboard
was not reaching VICE at all it leaves warp ON (which is how this rig ran its
first trial -- a screensaver had grabbed the keyboard), and pressed twice it
also leaves warp on.  Both look like a working run that is simply timing
strangely.

So measure instead.  The KERNAL jiffy clock at $A0-$A2 advances 60 times a
second on an NTSC machine, and the ratio to wall-clock time is what warp
changes.  Read it, toggle only if it is fast, and read it again to confirm.
Note the reading is a LOWER bound on the true rate: entering the monitor pauses
the emulator, so some wall-clock time passes with the jiffy clock stopped.
That only ever makes warp look slower than it is, so a reading near 60 cannot
be a warped machine -- which is the direction that matters here.
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicemon import Mon
import novaterm

NTSC_JIFFIES = 60.0
FAST = 1.5 * NTSC_JIFFIES        # comfortably above 1x, well below any warp

def jiffies():
    m = Mon(29876)
    v = m.peek(0x00A0, 3)
    m.resume(); m.k.close()
    return (v[0] << 16) | (v[1] << 8) | v[2]

def rate(secs=3.0):
    a = jiffies(); t0 = time.time()
    time.sleep(secs)
    return (jiffies() - a) / (time.time() - t0)

def main():
    before = rate()
    print("jiffies/sec: %.0f" % before)
    if before <= FAST:
        print("already at real speed")
        return 0
    nt = novaterm.NovaTerm()
    nt.keys.focus(); nt.keys.combo("Alt_L", "w"); time.sleep(2.0)
    after = rate()
    print("jiffies/sec after Alt+W: %.0f" % after)
    if after > FAST:
        print("FATAL: still warped -- are keystrokes reaching VICE?", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
