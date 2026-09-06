#!/usr/bin/env bash
# Run a set of protocol/direction pairs through NovaTerm and VERIFY THE BYTES.
#
# A screen that says "complete" is not a result -- the whole point of the
# 1775-byte PUNTEST.SEQ payload is that a framing defect shows up as changed
# bytes, not as an error message.  So every run ends in a byte comparison
# against the payload, and a run with no output file is a failure however
# cheerful the screen was.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
LINK="${LINK:-telnet}"
OUT="${OUT:-$HERE/sweep-results}"
mkdir -p "$OUT"

# Keep the evidence.  `one-run.sh` truncates gateway.log and tcpser.log on
# every start, so a failure diagnosed after the next run began had already
# lost its wire trace -- that happened, and cost a re-run.  The gateway's own
# ethernetgateway.log accumulates and is copied too, since it is the only one
# that survives on its own.
archive() { # proto dir
    local proto="$1" dir="$2"
    cp -f gateway.log        "$OUT/$proto-$dir.gateway.log"  2>/dev/null
    cp -f tcpser.log         "$OUT/$proto-$dir.tcpser.log"   2>/dev/null
    cp -f run/ethernetgateway-data/ethernetgateway.log \
                             "$OUT/$proto-$dir.egw.log"      2>/dev/null
    return 0
}

verify() { # proto dir
    local proto="$1" dir="$2"
    if [ "$dir" = download ]; then
        cp -f run/xfer.d64 "$OUT/$proto-$dir.d64" 2>/dev/null || return 1
        python3 d64read.py "$OUT/$proto-$dir.d64" > "$OUT/$proto-$dir.dir" 2>&1
        # **Never select the downloaded file by name.**  one-run.sh seeds the
        # disk with PUNTEST.SEQ before every run, so a name match finds the
        # SEED and passes whatever the transfer did -- it reported a total
        # ZMODEM failure as IDENTICAL.  verify-run.py picks the unclosed
        # (splat) entry, which is the one the receiver just wrote.
        python3 verify-run.py payloads/PUNTEST.SEQ "$OUT/$proto-$dir.d64"
        return $?
    else
        # **Never select the uploaded file by name either.**  The gateway
        # saves the first file of a batch under the SENDER's own name
        # (`file_transfer_upload`, idx == 0), so a ZMODEM or YMODEM upload
        # lands as whatever NovaTerm called it and not as the name typed at
        # the Filename prompt -- a sweep matching that name reports a
        # byte-perfect upload as a failure.  verify-upload.py identifies it by
        # provenance and archives what it graded.
        python3 verify-upload.py payloads/PUNTEST.SEQ \
            run/ethernetgateway-data/transfer payloads "$OUT/$proto-$dir."
        return $?
    fi
}

for spec in "$@"; do
    proto="${spec%%:*}"; dir="${spec##*:}"
    echo "=============== $proto $dir over $LINK"
    ./one-run.sh "$proto" "$dir" "$LINK" > "$OUT/$proto-$dir.screen" 2>&1
    tail -20 "$OUT/$proto-$dir.screen"
    archive "$proto" "$dir"
    echo "--- bytes:"; verify "$proto" "$dir" || echo "    FAIL"
done
