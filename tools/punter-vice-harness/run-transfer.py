#!/usr/bin/env python3
"""One automated transfer against NovaTerm, in either direction.

    run-transfer.py <protocol> <download|upload> [dial]

`protocol` names both ends at once: the entry to pick in NovaTerm's own
protocol menu, and the key the gateway's transfer menu wants.  Keeping the two
in one table is the point -- running a Punter test against a Zmodem receiver
looks exactly like a protocol defect, and NovaTerm resets to Zmodem on load.
"""
import sys, time, novaterm

# name -> (index in NovaTerm's Select-protocol list, gateway menu key)
# NovaTerm's list, in order: Zmodem, Ymodem batch, Ymodem-g, Xmodem-CRC,
# Xmodem-1k, Xmodem-1k-g, Punter, Multi-Punter, Kermit, WXmodem recv, Quit.
PROTOCOLS = {
    'zmodem':    (0, 'z'),
    'ymodem':    (1, 'y'),
    'xmodem':    (3, 'x'),
    'xmodem1k':  (4, '1'),
    'punter':    (6, 'p'),
    'kermit':    (8, 'k'),
}

def started(nt):
    """Is NovaTerm already receiving?

    ZMODEM auto-download means the transfer can be under way before the
    harness would have started it, and the key that starts it by hand (C=) is
    also the key that aborts one in flight.  So ask the screen.  The transfer
    display is the same for every protocol -- a "bytes recv:" counter -- and
    the reversed capital in "Zmodem download" decodes to '.', so match on the
    counter rather than on the protocol's name.
    """
    scr = nt.text()
    return any('ytes recv' in l or 'ytes rec' in l for l in scr)


def set_protocol(nt, index):
    nt.keys.focus(); nt.keys.combo('Tab', 'p'); time.sleep(8.0)
    here = 0                     # the list always opens on Zmodem
    for _ in range(index - here):
        nt.press('Down', 0.35)
    nt.press('Return', 3.0)
    time.sleep(10.0)             # NovaTerm loads the protocol module from disk

def main():
    if len(sys.argv) < 3 or sys.argv[1] not in PROTOCOLS:
        print(__doc__); print("protocols:", ", ".join(sorted(PROTOCOLS)))
        return 2
    name, direction = sys.argv[1], sys.argv[2]
    dial = sys.argv[3] if len(sys.argv) > 3 else '1'
    index, key = PROTOCOLS[name]

    nt = novaterm.NovaTerm()
    nt.ensure_terminal_mode()
    set_protocol(nt, index)
    nt.dial(dial)
    nt.inst_del(3.5)
    nt.type('n', 3.0)
    nt.type('f', 3.0)

    if direction == 'download':
        nt.type('d', 4.0)
        if not any('elect' in l for l in nt.text()):
            print("no file list:", [l for l in nt.text() if l.strip()][-5:]); return 1
        nt.type('4\n', 3.0)                 # PUNTEST.SEQ
        nt.type(key, 4.0)
        time.sleep(1.0)
        # **Do not press C= if the receiver is already running.**  C= is
        # NovaTerm's abort key -- the download screen says so -- and it is
        # polled continuously by `readline`/`rzdatexi` in the protocol
        # modules.  ZMODEM auto-downloads: `rzauthdr` catches the gateway's
        # ZRQINIT and NovaTerm answers ZRINIT on its own, about a second after
        # the gateway is told to send.  Pressing C= D four seconds later
        # therefore did not start the transfer, it CANCELLED one already in
        # its data phase -- measured at tcpser: ZRINIT, ZRPOS, our first data
        # subpacket, then eight CAN and eight backspaces exactly as the combo
        # was struck.  Two runs were read as a ZMODEM framing defect on that
        # evidence, and the sender was fine.
        if not started(nt):
            nt.keys.focus(); nt.keys.combo('Tab', 'd')
            time.sleep(4.0)
        # **Ask the dialog what it wants.**  It differs per protocol: Punter
        # and the XMODEM family prompt for a save-as name, while YMODEM and
        # ZMODEM carry the name in band and prompt for nothing.  Typing a name
        # blindly at those two sends it to the terminal instead, the receiver
        # never starts, and the gateway reports "Timeout waiting for receiver
        # to start" -- which looks like the protocol failing to negotiate.
        if any('.ile:' in l or 'ile:' in l for l in nt.text()):
            nt.type('%s\n' % name[:8], 2.0)
        # NovaTerm's download dialog asks different follow-up questions per
        # protocol, and any pause here is spent against the gateway's
        # 45-second window: answer them immediately or the transfer aborts
        # before the receiver has sent its first byte, which reads as a
        # protocol failure and is a lost race.
        for _ in range(3):
            scr = nt.text()
            if any('prg' in l for l in scr):          # "Type (prg,seq,usr):"
                nt.type('s\n', 1.2)
            elif any('eplace' in l for l in scr):     # "Replace?"
                nt.type('y', 1.2)
            else:
                break
    else:
        nt.type('u', 4.0)
        nt.type('%sup.seq\n' % name[:6], 3.5)
        nt.type(key, 4.0)
        time.sleep(1.0)
        nt.keys.focus(); nt.keys.combo('Tab', 'u')
        time.sleep(5.0)
        # **Ask the dialog what it wants**, exactly as the download path does.
        # Typing 'puntest' blindly is what made every non-Punter upload fail:
        # the gateway sat resending ZRINIT while NovaTerm's dialog waited for
        # something else, and the run read as a protocol failure when the
        # transfer had never been started at all.  Dump the dialog either way
        # -- the screen is the only record of what it asked.
        dlg = [l for l in nt.text() if l.strip()]
        print("  upload dialog:", flush=True)
        for l in dlg[-8:]:
            print('    |%s|' % l, flush=True)
        selector = (any('irectory' in l for l in dlg)
                    and any('elected' in l for l in dlg))
        if selector:
            # The batch protocols (ZMODEM, YMODEM) carry the name in band, so
            # NovaTerm shows a two-column file SELECTOR instead of asking for
            # one: f3 adds the highlighted entry to "selected", f7 starts.
            # Typing a filename here goes to the terminal, the upload never
            # begins, and the gateway reports a negotiation timeout -- which
            # reads as a protocol defect rather than as a dialog we never
            # answered.
            nt.press('F3', 1.5)
            nt.press('F7', 3.0)
        else:
            nt.type('puntest\n', 3.0)
        # Follow-ups differ per protocol, and every pause here is spent
        # against the gateway's negotiation window.
        for _ in range(3):
            scr = nt.text()
            if any('prg' in l for l in scr):
                nt.type('s\n', 1.2)
            elif any('eplace' in l for l in scr):
                nt.type('y', 1.2)
            else:
                break

    for _ in range(18):
        time.sleep(10)
        s = nt.text()
        if any('omplete' in l or 'rror' in l or 'bort' in l or 'ailed' in l for l in s):
            break
    for l in nt.text():
        if l.strip():
            print('|%s|' % l)
    return 0

if __name__ == '__main__':
    sys.exit(main())
