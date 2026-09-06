"""The one byte comparison both verifiers use.

Download and upload are checked by two scripts because the file is fetched
from two different places -- a D64 directory and the gateway's transfer
directory -- but *what counts as identical* must not be decided twice.  A
second copy of this rule would drift, and the difference would then read as a
protocol defect on whichever side was checked by the stale copy.
"""


def compare(body, want):
    """Is `body` the payload?  Returns (ok, description).

    XMODEM and XMODEM-1K carry no length field, so the last block is padded to
    a 128-byte boundary with SUB and the receiver keeps it.  That is correct
    behaviour, not corruption -- but it is reported out loud with the byte
    count rather than trimmed quietly, because a silent trim would also hide a
    genuinely truncated transfer.
    """
    if body == want:
        return True, "%d bytes identical" % len(body)
    trimmed = body
    while trimmed and trimmed[-1] == 0x1A:
        trimmed = trimmed[:-1]
    pad = len(body) - len(trimmed)
    if trimmed == want and pad < 128:
        return True, ("%d bytes identical + %d bytes of SUB padding "
                      "(XMODEM has no length field)" % (len(want), pad))
    return False, "%d bytes, expected %d — DIFFERS" % (len(body), len(want))
