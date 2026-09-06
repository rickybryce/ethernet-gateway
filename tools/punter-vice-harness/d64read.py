#!/usr/bin/env python3
"""Pull a file out of a .d64 by walking its sector chain.

NovaTerm leaves a completed download as a splat (unclosed) entry: `c1541
-read` refuses it and `c1541 -validate` DELETES it.  The data blocks are all
there, so read them directly.  Always work on a COPY.
"""
import sys
SPT = [21]*17 + [19]*7 + [18]*6 + [17]*5
def off(t, s): return (sum(SPT[:t-1]) + s) * 256

def entries(d):
    t, s, out = 18, 1, []
    seen = set()
    while t and (t, s) not in seen:
        seen.add((t, s))
        blk = d[off(t,s):off(t,s)+256]
        for e in range(8):
            ent = blk[2+e*32 : 2+e*32+32]
            name = bytes(ent[3:19]).rstrip(b'\xa0').decode('latin1').strip('\x00')
            if name.strip():
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
