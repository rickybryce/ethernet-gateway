#!/usr/bin/env python3
"""Read NovaTerm's YMODEM receive buffer while it is rejecting a block.

`batch.src`: mem = $C800 is the data buffer, header = mem-5 = $C7FB holds the
five framing bytes (type, block num, complement, CRC hi, CRC lo).

This is the measurement that separates "NovaTerm rejected a block it received
intact" from "the block never arrived intact".  A trace taken at tcpser cannot
tell those apart -- it stops one hop short of the machine doing the rejecting.
"""
import sys, time
from vicemon import Mon

m = Mon(29876)
hdr = m.peek(0xC7FB, 5)
size = 1024 if hdr[0] == 0x02 else 128
data = m.peek(0xC800, size)
m.resume(); m.k.close()
names = {0x01: 'SOH', 0x02: 'STX'}
print("header: %s num=%d ~num=%02X crc=%02X%02X"
      % (names.get(hdr[0], '%02X' % hdr[0]), hdr[1], hdr[2], hdr[3], hdr[4]))
open(sys.argv[1] if len(sys.argv) > 1 else '/tmp/novabuf.bin', 'wb').write(bytes(data))
print("wrote %d data bytes" % len(data))
