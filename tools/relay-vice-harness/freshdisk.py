#!/usr/bin/env python3
"""Give NovaTerm a fresh transfer disk WITHOUT restarting the emulator.

Ricky's constraint is that VICE only restarts when the link changes, but every
download run still needs a clean disk: `verify-run.py` identifies this run's
file as the **unclosed (splat)** directory entry, and with a disk that carries
the previous runs' downloads there are several of those -- so the grader would
re-grade old transfers as this one's.  That is the "leftovers graded as this
run's" trap the sweep scripts already carry a comment about, one layer down.

Swapping the disk is not restarting the machine: `detach 10` flushes and
closes the image (which is also what makes the file on disk safe to read),
c1541 rebuilds it, and `attach` puts it back.  To the C64 that is a person
changing a floppy, which is exactly what it is.
"""
import os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicemon import Mon

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "run", "xfer.d64")
SEED = os.path.join(HERE, "payloads", "PUNTEST.SEQ")

def main():
    m = Mon(29876)
    m.cmd("detach 10", 2.0)
    m.resume(); m.k.close()
    time.sleep(1.0)

    subprocess.run(["c1541", "-format", "xfer,01", "d64", IMG],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(["c1541", "-attach", IMG, "-write", SEED, "puntest,s"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    m = Mon(29876)
    m.cmd('attach "%s" 10' % IMG, 2.0)
    m.resume(); m.k.close()
    time.sleep(1.0)

    # Positive control: say what is on the disk we just handed over, so a run
    # that fails later cannot be blamed on a disk nobody looked at.
    out = subprocess.run(["c1541", "-attach", IMG, "-dir"],
                         capture_output=True, text=True).stdout
    print("fresh disk:", " ".join(out.split())[:200])
    return 0

if __name__ == "__main__":
    sys.exit(main())
