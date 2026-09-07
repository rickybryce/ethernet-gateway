#!/usr/bin/env python3
"""Pull a file out of a .d64 by walking its sector chain.

NovaTerm leaves a completed download as a splat (unclosed) entry: `c1541
-read` refuses it and `c1541 -validate` DELETES it.  The data blocks are all
there, so read them directly.  Always work on a COPY.
"""
import sys
SPT = [21]*17 + [19]*7 + [18]*6 + [17]*5
def off(t, s): return (sum(SPT[:t-1]) + s) * 256


def petscii_name(raw):
    """Render a CBM directory name as the C64 itself would show it.

    **Not `latin1`.**  A CBM name is PETSCII, and decoding it as Latin-1 turns
    every letter with the high bit set into an accented Roman one -- a
    perfectly ordinary `PUNTEST.SEQ` was reported here as `ÐÕÎÔÅÓÔ.ÓÅÑ`, which
    reads as a corrupted filename and was asked about as one.

    The high bit is not damage: PETSCII has the alphabet twice, at
    `41`-`5A` and again at `C1`-`DA`, and which one a name lands in says only
    where it came from.  A name typed at the C64's keyboard arrives in the low
    range; a name that came **in band on the wire** -- a YMODEM block 0 or a
    ZMODEM ZFILE header -- is converted from ASCII by the receiving terminal,
    and NovaTerm picks the high range.  Both display identically on a real
    C64, so both are folded to the same letters here.

    Anything outside those two ranges is escaped rather than guessed at, so a
    name that really is damaged still looks damaged.
    """
    out = []
    for b in raw:
        if 0xC1 <= b <= 0xDA:          # PETSCII shifted uppercase
            out.append(chr(b & 0x7F))
        elif 0x20 <= b <= 0x5F:        # digits, punctuation, unshifted letters
            out.append(chr(b))
        else:
            out.append('\\x%02X' % b)
    return ''.join(out)

def entries(d):
    t, s, out = 18, 1, []
    seen = set()
    while t and (t, s) not in seen:
        seen.add((t, s))
        blk = d[off(t,s):off(t,s)+256]
        for e in range(8):
            ent = blk[2+e*32 : 2+e*32+32]
            raw = bytes(ent[3:19]).rstrip(b'\xa0').replace(b'\x00', b'')
            name = petscii_name(raw)
            # **Skip DEL slots.**  A scratched entry keeps its old name bytes
            # and its data pointer, so it reads back as a file of whatever
            # length the chain still reaches -- the CCGMS disk has eight of
            # them and they arrived in a grading report as eight 1016-byte
            # near-misses against the payload.  The low nibble of the file
            # type is 0 for DEL; a real file is SEQ/PRG/USR/REL (1-4).
            if name.strip() and (ent[0] & 0x0F) != 0:
                out.append((name, ent[0], ent[1], ent[2]))
        t, s = blk[0], blk[1]
    return out

def extract(d, ft, fs):
    data, seen = bytearray(), set()
    while ft and (ft, fs) not in seen:
        seen.add((ft, fs))
        blk = d[off(ft,fs):off(ft,fs)+256]
        nt, ns = blk[0], blk[1]
        if nt == 0:
            data += blk[2:1+ns]; break
        data += blk[2:256]; ft, fs = nt, ns
    return bytes(data)

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    want = sys.argv[2].lower() if len(sys.argv) > 2 else None
    for name, ftype, ft, fs in entries(d):
        if want and want not in name.lower():
            continue
        body = extract(d, ft, fs)
        print("%-16s type=%02X  %d bytes" % (name, ftype, len(body)))
        if len(sys.argv) > 3:
            open(sys.argv[3], 'wb').write(body)
