#!/usr/bin/env python3
"""Drive one NovaTerm for the peer-to-peer test.

  peer.py term              -- get to terminal mode and sit there
  peer.py dial <target>     -- terminal mode, then ATDT <target>
  peer.py screen            -- print the C64 screen
"""
import sys, time
sys.path.insert(0, "/home/ricky/peer-vice")
import novaterm

def show(nt, tag):
    print("---- %s ----" % tag)
    for l in nt.text():
        if l.strip():
            print("|" + l + "|")

cmd = sys.argv[1] if len(sys.argv) > 1 else "screen"
nt = novaterm.NovaTerm()
if cmd == "screen":
    show(nt, "screen")
elif cmd == "term":
    nt.ensure_terminal_mode()
    time.sleep(1.0)
    show(nt, "terminal mode")
elif cmd == "dial":
    target = sys.argv[2]
    nt.ensure_terminal_mode()
    time.sleep(1.0)
    nt.dial(target, settle=14.0)
    show(nt, "after ATDT %s" % target)
