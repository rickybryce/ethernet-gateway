#!/usr/bin/env bash
# Reverse direction: the MASTER's C64 sends, the SLAVE's C64 receives.
set -u
export SSH_AUTH_SOCK=/run/user/1000/keyring/ssh
P="${1:?protocol}"; NAME="${2:-revrecv}"
SLAVE=192.168.1.141; MASTER=192.168.1.178
R() { timeout 300 ssh -o BatchMode=yes ricky@"$1" "cd ~/peer-vice && DISPLAY=:0 python3 $2" 2>&1; }
OUT="$(mktemp -d)"
echo "--- reset both, arm the answering side"
R $MASTER "reset.py arm" | tail -2
R $SLAVE  "reset.py"     | tail -2
echo "--- dial (141 still places the call; either side may then send)"
R $SLAVE  "peer.py dial \"A@$MASTER\"" | tail -2
echo "--- select $P on both"
( R $MASTER "xfer.py proto $P" > $OUT/pm 2>&1 ) & ( R $SLAVE "xfer.py proto $P" > $OUT/ps 2>&1 ) & wait
echo "--- receiver on the SLAVE, sender on the MASTER"
( R $SLAVE  "xfer.py recv $P $NAME"     > $OUT/r 2>&1 ) & RP=$!
sleep 10
( R $MASTER "xfer.py send $P puntest"   > $OUT/s 2>&1 ) & SP=$!
wait $RP $SP
echo "=== RECEIVER (141) ==="; tail -7 $OUT/r
echo "=== SENDER (178) ==="; tail -7 $OUT/s
