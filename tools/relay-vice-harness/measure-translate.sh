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

# A `sed -i` that matches nothing succeeds, so the old version could announce a
# mode it had not set and then measure whatever was already in force.  Read the
# key back and require it to say what we asked for.
set_translate() {
    ssh $SLAVE "sed -i 's|^gateway_petscii_translate = .*|gateway_petscii_translate = $1|' $CONF; \
                grep -c '^gateway_petscii_translate = $1\$' $CONF" | tr -d ' \r' \
        | grep -qx 1 || {
            echo "FATAL: could not set gateway_petscii_translate = $1 on $SLAVE" >&2
            exit 1
        }
    echo "    slave: gateway_petscii_translate = $1"
}

# Put the slave back however this exits: an interrupted measurement used to
# leave it in translating mode for whatever ran next, which is a setting nobody
# chose silently deciding a later result.
trap 'set_translate false >/dev/null 2>&1 || true' EXIT

echo "--- setting the slave to the DEFAULT translating mode"
set_translate true
LINK=telnet OUT="$HERE/results/telnet-translating" ./relay-sweep.sh xmodem:download xmodem:upload
rc=$?

echo "--- restoring the raw (Commodore-aware) mode"
set_translate false
echo "MEASUREMENT RC=$rc"
# Exit with the measurement's own status: ending on `echo` made this script
# report success whatever the cells did.
exit "$rc"
