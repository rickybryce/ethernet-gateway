#!/usr/bin/env bash
# One protocol, one direction, from a guaranteed-clean start.
#
# NovaTerm keeps state across a run -- an aborted transfer leaves a dialog up,
# the menu remembers where it was, the protocol resets to Zmodem -- and every
# attempt to recover in-place cost more time than a restart does.  So each run
# gets a fresh emulator.
#
#   ./one-run.sh <protocol> <download|upload> [serial|telnet]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO="${1:?protocol}"; DIR="${2:?download|upload}"; LINK="${3:-telnet}"
cd "$HERE"

# **Scope the kill to this harness's own emulator.**  A bare `pgrep -x x64sc`
# kills every VICE on the machine, including one a developer has open for
# something else -- the gateway two lines down is already identified by its
# working directory, which is this project's documented rule, and the same
# rule applies here.  VICE is started from this directory, so its cwd names it.
for p in $(pgrep -x x64sc); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *punter-vice-harness*) kill "$p" 2>/dev/null;; esac
done
for p in $(pgrep -x ethernetgateway); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *punter-vice-harness*) kill "$p" 2>/dev/null;; esac
done
for p in $(pgrep -x tcpser); do
    d=$(readlink /proc/$p/cwd 2>/dev/null)
    case "$d" in *punter-vice-harness*) kill "$p" 2>/dev/null;; esac
done
sleep 3

# A fresh transfer disk every time: NovaTerm asks "Replace?" otherwise, and
# that question is asked inside the gateway's 45-second window.
c1541 -format "xfer,01" d64 run/xfer.d64 >/dev/null 2>&1
c1541 -attach run/xfer.d64 -write payloads/PUNTEST.SEQ "puntest,s" >/dev/null 2>&1
# **Clear the slate; do not pattern-match it.**  This used to delete
# `*up.seq` and `*up*.usr`, but the gateway saves an upload under the
# SENDER's name when the protocol carries one, and validate_filename drops
# the dot -- so a YMODEM upload landed as `ymodemupseq` and `puntest`, neither
# of which matched, and both survived into the next run.  The sweep identifies
# this run's output as "whatever is not seeded", so it then graded the
# leftovers: an XMODEM run that saved nothing at all was reported as a PASS,
# twice.  Everything removed here is either re-seeded just below or placed by
# the gateway itself on first launch.
find run/ethernetgateway-data/transfer -maxdepth 1 -type f \
    ! -name 'EGT8080.COM' ! -name 'EGT80.COM' -delete
# Refresh the payloads unconditionally.  start-gateway.sh seeds them only when
# absent, which is right for a long-lived rig and wrong for a test: changing
# payloads/PUNTEST.SEQ then had no effect, and an experiment that varied the
# input silently ran against the old one.
cp -f payloads/* run/ethernetgateway-data/transfer/ 2>/dev/null

if [ "$LINK" = serial ]; then
    sed -i 's/^serial_a_enabled = .*/serial_a_enabled = true/' run/ethernetgateway-data/egateway.conf
    # **Make the wire.**  `serial_a_port` names run/ttyGW and VICE is handed
    # run/ttyC64; both are symlinks socat creates, and nothing created them --
    # the first serial run made the pair by hand, and it died at the next
    # reboot leaving two symlinks pointing at /dev/pts entries that no longer
    # exist.  VICE then opens nothing and the gateway cannot open its port,
    # which presents as a serial link that simply does not carry: no CONNECT,
    # no bytes, and nothing in either log naming a cause.
    #
    # It has to happen before the gateway starts, because the gateway opens
    # its serial port at launch and a missing port is not retried.  `raw` is
    # not optional: a cooked line discipline maps CR to LF and would corrupt
    # every block of every protocol, identically on each retry, past any CRC.
    # **Wait for the old socat to actually die before making a new pair.**
    # `pkill` only sends the signal, and socat REMOVES its `link=` symlinks on
    # the way out -- so killing it, creating a new pair, and letting the old
    # one exit afterwards has the dying process unlink the symlinks the new one
    # just made.  The pair then vanishes under a run that had already checked
    # for it, and the guard below reports a failure that is really a race.
    pkill -f "socat.*ttyGW" 2>/dev/null
    for _ in $(seq 1 50); do
        pgrep -f "socat.*ttyGW" >/dev/null 2>&1 || break
        sleep 0.1
    done
    rm -f run/ttyGW run/ttyC64
    socat pty,raw,echo=0,link="$HERE/run/ttyGW" \
          pty,raw,echo=0,link="$HERE/run/ttyC64" > socat.log 2>&1 &
    # socat creates the links asynchronously; a gateway that wins the race
    # finds no port at all.  Wait for both, and say so rather than starting a
    # run that cannot work.
    for _ in $(seq 1 50); do
        [ -e run/ttyGW ] && [ -e run/ttyC64 ] && break
        sleep 0.1
    done
    if [ ! -e run/ttyGW ] || [ ! -e run/ttyC64 ]; then
        echo "FATAL: socat did not create the PTY pair; see socat.log" >&2
        exit 1
    fi
    RS=(-rsdev1 "$HERE/run/ttyC64" -rsdev1baud 2400); DIALNO=ethernetgateway
else
    sed -i 's/^serial_a_enabled = .*/serial_a_enabled = false/' run/ethernetgateway-data/egateway.conf
    RS=(-rsdev1 "127.0.0.1:25232" -rsdev1ip232 -rsdev1baud 2400); DIALNO=1
fi

# NOT `> gateway.log`: start-gateway.sh already tees to that file, and two
# writers both starting at offset 0 interleave and overwrite each other.  It
# duplicated ACK lines and truncated others, which made three cleanly ACKed
# XMODEM blocks look like a sender restarting in a loop -- a defect that was
# never there.
GATEWAY_BIN=/home/ricky/xmodem/target/debug/ethernetgateway nohup ./start-gateway.sh >/dev/null 2>&1 &
sleep 6
[ "$LINK" = telnet ] && { nohup ./start-tcpser.sh > tcpser.log 2>&1 & sleep 3; }

DISPLAY=:0 nohup x64sc -warp -acia1 -acia1base 0xDE00 -acia1irq 1 -acia1mode 1 -myaciadev 0 \
    "${RS[@]}" -remotemonitor -remotemonitoraddress ip4://127.0.0.1:29876 \
    -drive10type 1541 -10 run/xfer.d64 \
    -autostart "$HOME/Documents/NovaTerm/novaterm_9.6c.d64" > /tmp/vice.log 2>&1 &

sleep 30
for i in 1 2 3 4 5 6; do
    r=$(DISPLAY=:0 timeout 40 python3 -c "
import novaterm
nt=novaterm.NovaTerm(); s=nt.selected()
print(novaterm.MAIN_ITEMS[s] if s is not None else 'loading')" 2>/dev/null | grep -v "X protocol\|Xlib" | tail -1)
    [ "$r" != "loading" ] && break
    sleep 15
done
DISPLAY=:0 timeout 60 python3 -c "
import novaterm,time; nt=novaterm.NovaTerm(); nt.keys.focus(); nt.keys.combo('Alt_L','w'); time.sleep(2)" \
    2>/dev/null >/dev/null
# **Report the transfer's status, not grep's.**  Ending on a pipe made this
# script exit with the filter's status: `grep -v` answers 0 when it printed
# something and 1 when it did not, so a failed run whose output happened to
# contain a line looked like a success, and a silent success looked like a
# failure.  `sweep.sh` refuses to grade a run that did not complete, so this
# status has to be the real one.
DISPLAY=:0 timeout 560 python3 run-transfer.py "$PROTO" "$DIR" "$DIALNO" 2>&1 \
    | grep -v "X protocol\|Xlib"
exit "${PIPESTATUS[0]}"
