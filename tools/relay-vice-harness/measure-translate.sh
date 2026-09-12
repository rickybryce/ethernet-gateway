#!/usr/bin/env bash
# What does the DEFAULT (translating) proxy do to a transfer over the relay?
#
# The 12-cell telnet leg runs with gateway_petscii_translate = false, which
# makes the slave a pipe.  `true` is the shipped default and the setting a user
# meets first, so what it does to a file transfer is worth RECORDING rather
# than reasoning about -- CLAUDE.md says a translating path "could never carry
# a transfer", and this is the measurement behind that sentence on this rig.
set -u
export SSH_AUTH_SOCK=/run/user/1000/keyring/ssh
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
SLAVE=192.168.1.141
CONF=/home/ricky/relay-vice/run/ethernetgateway-data/egateway.conf

set_translate() {
    ssh $SLAVE "sed -i 's|^gateway_petscii_translate = .*|gateway_petscii_translate = $1|' $CONF && grep -n '^gateway_petscii_translate' $CONF"
}

echo "--- setting the slave to the DEFAULT translating mode"
set_translate true
LINK=telnet OUT="$HERE/results/telnet-translating" ./relay-sweep.sh xmodem:download xmodem:upload
rc=$?

echo "--- restoring the raw (Commodore-aware) mode"
set_translate false
echo "MEASUREMENT RC=$rc"
