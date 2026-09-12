#!/usr/bin/env python3
"""Give NovaTerm a fresh transfer disk WITHOUT restarting the emulator.

Ricky's constraint is that VICE only restarts when the link changes, but every
download run still needs a clean disk: `verify-run.py` identifies this run's
file as the **unclosed (splat)** directory entry, and with a disk that carries
the previous runs' downloads there are several of those -- so the grader would
re-grade old transfers as this one's.  That is the "leftovers graded as this
run's" trap the sweep scripts already carry a comment about, one layer down.

Swapping the disk is not restarting the machine: detach flushes and closes the
image (which is also what makes the file on disk safe to read), c1541 rebuilds
it, and attach puts it back.  To the C64 that is a person changing a floppy,
which is exactly what it is.

**THE UNIT NUMBER IS HEX.**  VICE's monitor parses numbers as hex, so `detach
10` asks for device *sixteen* and answers "Unknown device 16." -- which this
script sent for weeks without reading the reply.  The disk was therefore never
swapped: c1541 rebuilt the FILE while VICE still had it attached, the drive went
on writing its own stale view back over it, and old directory entries
reappeared.  The visible symptom was NovaTerm asking "Replace?" for a file on a
disk formatted seconds earlier.  Unit 10 is `a`.

The check below is the other half.  The old positive control read the image
with c1541 -- the wrong SIDE of the swap: the file was genuinely clean every
time, and the emulator's view of it was what had gone stale.  So a marker is
written into the image and the sweep requires it to still be there afterwards:
if VICE is holding a different disk, the marker is what disappears.
"""
import os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vicemon import Mon

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "run", "xfer.d64")
SEED = os.path.join(HERE, "payloads", "PUNTEST.SEQ")
UNIT = "a"                      # device 10, in the monitor's hex

def monitor(cmd, wait=2.0):
    """Run one monitor command and REFUSE a reply that reports a problem.

    Both spellings of a bad unit print nothing but a prompt on success, so the
    absence of output proves nothing on its own -- but the failures do announce
    themselves, and nobody was listening.
    """
    m = Mon(29876)
    out = m.cmd(cmd, wait).decode("latin1", "replace")
    m.resume(); m.k.close()
    for bad in ("Unknown device", "Failed", "Cannot", "not found"):
        if bad in out:
            raise SystemExit("FATAL: monitor refused %r: %s" % (cmd, out.strip()))
    return out

def main():
    marker = "run%05d" % (int(time.time()) % 100000)

    monitor("detach %s" % UNIT)
    time.sleep(1.0)

    subprocess.run(["c1541", "-format", "xfer,01", "d64", IMG],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    subprocess.run(["c1541", "-attach", IMG, "-write", SEED, "puntest,s"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    # The marker: proof, later, that the disk the C64 wrote to is this one.
    mark_src = os.path.join(HERE, "run", ".marker")
    with open(mark_src, "w") as f:
        f.write(marker + "\n")
    subprocess.run(["c1541", "-attach", IMG, "-write", mark_src, "%s,s" % marker],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    monitor('attach "%s" %s' % (IMG, UNIT))
    time.sleep(1.0)

    out = subprocess.run(["c1541", "-attach", IMG, "-dir"],
                         capture_output=True, text=True).stdout
    if "puntest" not in out or marker not in out:
        raise SystemExit("FATAL: the disk we just built is not what we meant: %s"
                         % " ".join(out.split())[:200])
    print("fresh disk: seeded puntest, marker %s" % marker)
    return 0

if __name__ == "__main__":
    sys.exit(main())
