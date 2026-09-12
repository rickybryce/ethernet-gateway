#!/usr/bin/env python3
"""Arm this C64's modem to auto-answer: NovaTerm's own init string sends
S0=0, which disables it, so the config's S0 is overridden the moment the
terminal comes up.  Re-arm it from the terminal and prove it with S0?."""
import sys, time
sys.path.insert(0, "/home/ricky/peer-vice")
import novaterm
nt = novaterm.NovaTerm()
nt.ensure_terminal_mode(); time.sleep(1.0)
nt.type("ats0=1\n", 2.0)
nt.type("ats0?\n", 2.0)
for l in nt.text():
    if l.strip():
        print("|" + l + "|")
