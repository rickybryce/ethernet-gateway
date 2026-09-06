#!/usr/bin/env python3
"""Compare what NovaTerm actually WROTE against the payload.

    verify-run.py <payload> <d64> [...]

**Do not select the file by name.** `one-run.sh` seeds the transfer disk with
`PUNTEST.SEQ` before every run, so a name match finds the *seed* and reports a
byte-perfect result whatever the transfer did -- it did exactly that once, and
the pass meant nothing.  Two files of the same length and name are on that
disk and only one of them came down the wire.

The discriminator is the **splat (unclosed) entry**: the CBM directory sets
bit 7 of the file-type byte when a file is properly closed, and NovaTerm
leaves a completed download unclosed.  The seed, written by `c1541`, is
closed.  So the entry with bit 7 CLEAR is the one this run produced.
"""
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0] or '.')
from d64read import entries, extract

def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    want = open(sys.argv[1], 'rb').read()
    rc = 0
    for path in sys.argv[2:]:
        d = open(path, 'rb').read()
        wrote = [(n, t, ft, fs) for (n, t, ft, fs) in entries(d) if not (t & 0x80)]
        label = path.rsplit('/', 1)[-1]
        if not wrote:
            print(f"FAIL  {label}: nothing written by the receiver "
                  f"(only closed entries: {[n for n,_,_,_ in entries(d)]})")
            rc = 1
            continue
        if len(wrote) > 1:
            print(f"WARN  {label}: {len(wrote)} unclosed entries; comparing each")
        for (n, t, ft, fs) in wrote:
            body = extract(d, ft, fs)
            if body == want:
                print(f"PASS  {label}: {len(body)} bytes identical "
                      f"(entry {n!r}, type {t:02X})")
                continue
            # XMODEM and XMODEM-1K carry no length, so the last block is
            # padded to a 128-byte boundary with SUB and the receiver keeps
            # it.  That is correct behaviour, not corruption -- but say so
            # out loud with the byte count, rather than trimming quietly:
            # a silent trim would also hide a genuinely truncated transfer.
            trimmed = body
            while trimmed and trimmed[-1] == 0x1A:
                trimmed = trimmed[:-1]
            pad = len(body) - len(trimmed)
            if trimmed == want and pad < 128:
                print(f"PASS  {label}: {len(want)} bytes identical "
                      f"+ {pad} bytes of SUB padding (XMODEM has no length "
                      f"field) (entry {n!r}, type {t:02X})")
                continue
            print(f"FAIL  {label}: {len(body)} bytes, expected {len(want)} "
                  f"— DIFFERS (entry {n!r}, type {t:02X})")
            rc = 1
    return rc

if __name__ == '__main__':
    sys.exit(main())
