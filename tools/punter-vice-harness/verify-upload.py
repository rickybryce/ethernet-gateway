#!/usr/bin/env python3
"""Compare what the GATEWAY received against the payload.

    verify-upload.py <payload> <transfer-dir> <payloads-dir> [save-prefix]

The download verifier's rule, one level out: **do not select the file by
name.**  There are two reasons a name cannot identify an upload here.

* The gateway saves the first file of a batch under the *sender's* own name
  when the protocol carries one (`file_transfer_upload`, idx == 0), so a
  ZMODEM or YMODEM upload lands as whatever NovaTerm called it -- not as the
  name typed at the gateway's Filename prompt.  A sweep looking for that typed
  name finds nothing and reports a byte-perfect upload as a failure.
* `one-run.sh` copies `payloads/*` into the transfer directory before every
  run, so the payload itself is sitting there under its own name and any
  fuzzy match risks grading the run against the seed.

So identify by **provenance**: everything the harness and the gateway put
there is known (the payloads, and the two EGT terminal binaries the gateway
places on first launch), and whatever else appears is what came up the wire.

With a `save-prefix` the graded files are copied to `<prefix><name>` for the
archive.  Archiving is done here rather than in `sweep.sh` so that *which file
this run produced* is decided in exactly one place -- a second copy of the
rule in shell would be free to disagree about what it kept.
"""
import os, sys
sys.path.insert(0, __file__.rsplit('/', 1)[0] or '.')
from xfercheck import compare

# Placed by the gateway itself on first launch, never by a transfer.
SHIPPED = {'EGT8080.COM', 'EGT80.COM'}

def main():
    if not 4 <= len(sys.argv) <= 5:
        print(__doc__); return 2
    want = open(sys.argv[1], 'rb').read()
    xdir, pdir = sys.argv[2], sys.argv[3]
    save = sys.argv[4] if len(sys.argv) == 5 else None
    seeded = set(os.listdir(pdir)) | SHIPPED
    got = [f for f in sorted(os.listdir(xdir))
           if f not in seeded and os.path.isfile(os.path.join(xdir, f))]
    if not got:
        print(f"FAIL  nothing new in {xdir} — the upload never reached the "
              f"gateway (seeded: {sorted(seeded)})")
        return 1
    if len(got) > 1:
        print(f"WARN  {len(got)} new files; comparing each: {got}")
    rc = 0
    for f in got:
        body = open(os.path.join(xdir, f), 'rb').read()
        if save:
            open(save + f, 'wb').write(body)
        ok, how = compare(body, want)
        print(f"{'PASS' if ok else 'FAIL'}  {f}: {how}")
        if not ok:
            rc = 1
    return rc

if __name__ == '__main__':
    sys.exit(main())
