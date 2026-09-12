#!/usr/bin/env python3
"""Prove the peer link both ways without a protocol in the way.

  linktest.py back        -- C= Z out of a transfer screen into terminal mode,
                             WITHOUT hanging up (the carrier must survive)
  linktest.py say <text>  -- type text at the terminal
  linktest.py show        -- print the screen
"""
import sys, time
sys.path.insert(0, "/home/ricky/peer-vice")
import novaterm
nt = novaterm.NovaTerm()
cmd = sys.argv[1]
if cmd == 'back':
    nt.keys.focus(); nt.keys.combo('Tab', 'z'); time.sleep(3.0)
    if nt.at_menu():
        nt.choose("terminal mode"); time.sleep(2.0)
elif cmd == 'say':
    nt.type(sys.argv[2] + "\n", 2.0)
for l in nt.text():
    if l.strip():
        print("|" + l + "|")
