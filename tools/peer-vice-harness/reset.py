#!/usr/bin/env python3
"""Get this NovaTerm back to a known state: C= Z out of any transfer screen,
into terminal mode, then hang up.  A transfer screen left up is why the next
run's keystrokes land somewhere unexpected."""
import sys, time
sys.path.insert(0, "/home/ricky/peer-vice")
import novaterm
nt = novaterm.NovaTerm()
nt.keys.focus(); nt.keys.combo('Tab', 'z'); time.sleep(3.0)
nt.ensure_terminal_mode(); time.sleep(1.5)
nt.hangup()
if len(sys.argv) > 1 and sys.argv[1] == 'arm':
    nt.type("ats0=1\n", 2.0)
    nt.type("ats0?\n", 2.0)
for l in nt.text():
    if l.strip():
        print("|" + l + "|")
