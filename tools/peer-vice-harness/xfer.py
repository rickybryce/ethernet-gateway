#!/usr/bin/env python3
"""One side of a C64-to-C64 transfer through the gateway.

  xfer.py proto <name>              -- select a protocol module
  xfer.py recv  <proto> <savename>  -- arm the receiver
  xfer.py send  <proto> <filename>  -- start the sender

The two C64s are peers here: there is no gateway menu on the other end, so
nothing tells us what the far side is doing except this side's own screen.
"""
import sys, time
sys.path.insert(0, "/home/ricky/peer-vice")
import novaterm

# index in NovaTerm's Select-protocol list (opens on Zmodem)
PROTOS = {'zmodem':0, 'ymodem':1, 'xmodem':3, 'xmodem1k':4, 'punter':6, 'kermit':8}

def show(nt, tag):
    print("---- %s ----" % tag, flush=True)
    for l in nt.text():
        if l.strip():
            print("|" + l + "|", flush=True)

def set_protocol(nt, name):
    nt.keys.focus(); nt.keys.combo('Tab', 'p'); time.sleep(8.0)
    for _ in range(PROTOS[name]):
        nt.press('Down', 0.35)
    nt.press('Return', 3.0)
    time.sleep(10.0)   # NovaTerm loads the module from disk

def answer(nt, name, rounds=8, settle=1.5):
    """Answer whatever dialog is up, by reading it rather than replaying keys."""
    typed = False
    for _ in range(rounds):
        scr = [l for l in nt.text() if l.strip()]
        blob = ' '.join(scr)
        if 'irectory' in blob and 'elected' in blob:
            print("  dialog: file selector -> f3, f7", flush=True)
            nt.press('F3', 1.5); nt.press('F7', 3.0); return 'selector'
        if 'attern match' in blob:
            print("  dialog: settings -> RETURN", flush=True)
            nt.type('\n', 2.5); continue
        if 'prg' in blob:
            print("  dialog: type -> s", flush=True)
            nt.type('s\n', settle); continue
        if 'eplace' in blob:
            print("  dialog: replace -> y", flush=True)
            nt.type('y', settle); continue
        if not typed and ('ile:' in blob or 'ame:' in blob):
            print("  dialog: name -> %s" % name, flush=True)
            nt.type(name + '\n', 2.5); typed = True; continue
        break
    return 'done'

cmd = sys.argv[1]
nt = novaterm.NovaTerm()
if cmd == 'proto':
    set_protocol(nt, sys.argv[2]); show(nt, "protocol %s" % sys.argv[2])
elif cmd == 'recv':
    proto, name = sys.argv[2], sys.argv[3]
    nt.keys.focus(); nt.keys.combo('Tab', 'd'); time.sleep(4.0)
    print("  ->", answer(nt, name), flush=True)
    show(nt, "receiver armed")
elif cmd == 'send':
    proto, name = sys.argv[2], sys.argv[3]
    nt.keys.focus(); nt.keys.combo('Tab', 'u'); time.sleep(5.0)
    print("  ->", answer(nt, name), flush=True)
    show(nt, "sender started")
elif cmd == 'watch':
    time.sleep(float(sys.argv[2]) if len(sys.argv) > 2 else 30.0)
    show(nt, "screen")
