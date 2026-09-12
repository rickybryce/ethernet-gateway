#!/usr/bin/env bash
# One peer-to-peer transfer attempt, end to end.
#   run-peer.sh <protocol> [savename]
# Sender  = 141 (slave), file "puntest"
# Receiver= 178 (master)
set -u
export SSH_AUTH_SOCK=/run/user/1000/keyring/ssh
P="${1:?protocol}"; NAME="${2:-peerrecv}"
SLAVE=192.168.1.141; MASTER=192.168.1.178
R() { timeout 300 ssh -o BatchMode=yes ricky@"$1" "cd ~/peer-vice && DISPLAY=:0 python3 $2" 2>&1; }
OUT="$(mktemp -d)"

echo "--- reset both, arm the answering side"
R $MASTER "reset.py arm" | tail -3
R $SLAVE  "reset.py"     | tail -2
echo "--- dial"
R $SLAVE  "peer.py dial \"A@$MASTER\"" | tail -2
echo "--- select $P on both"
( R $MASTER "xfer.py proto $P" > $OUT/pm 2>&1 ) &
( R $SLAVE  "xfer.py proto $P" > $OUT/ps 2>&1 ) &
wait
echo "--- receiver, then sender 10s later"
( R $MASTER "xfer.py recv $P $NAME" > $OUT/r 2>&1 ) & RP=$!
sleep 10
( R $SLAVE  "xfer.py send $P puntest" > $OUT/s 2>&1 ) & SP=$!
wait $RP $SP
echo "=== RECEIVER ==="; tail -9 $OUT/r
echo "=== SENDER ==="; tail -9 $OUT/s
