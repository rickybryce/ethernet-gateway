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

verify() { # proto dir
    local proto="$1" dir="$2" got=""
    if [ "$dir" = download ]; then
        cp -f run/xfer.d64 "$OUT/$proto-$dir.d64" 2>/dev/null || return 1
        python3 d64read.py "$OUT/$proto-$dir.d64" puntest "$OUT/$proto-$dir.bin" \
            > "$OUT/$proto-$dir.dir" 2>&1
        got="$OUT/$proto-$dir.bin"
    else
        # The upload name is built by run-transfer.py as <first 6 of proto>up.seq
        local f
        f=$(ls -t run/ethernetgateway-data/transfer/ 2>/dev/null | grep -i 'up' | head -1)
        [ -z "$f" ] && return 1
        cp -f "run/ethernetgateway-data/transfer/$f" "$OUT/$proto-$dir.bin"
        got="$OUT/$proto-$dir.bin"
    fi
    [ -s "$got" ] || return 1
    if cmp -s "$got" payloads/PUNTEST.SEQ; then echo IDENTICAL; return 0; fi
    echo "DIFFERS ($(stat -c%s "$got") bytes vs $(stat -c%s payloads/PUNTEST.SEQ))"
    return 1
}

for spec in "$@"; do
    proto="${spec%%:*}"; dir="${spec##*:}"
    echo "=============== $proto $dir over $LINK"
    ./one-run.sh "$proto" "$dir" "$LINK" > "$OUT/$proto-$dir.screen" 2>&1
    tail -20 "$OUT/$proto-$dir.screen"
    echo "--- bytes: $(verify "$proto" "$dir" || echo FAIL)"
done
