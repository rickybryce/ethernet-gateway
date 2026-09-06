"""Drive NovaTerm 9.6c inside VICE, for the Punter interop gate.

Two channels, because neither alone is enough:

* **Reading** is VICE's remote monitor.  NovaTerm relocates its screen -- it is
  at `$8C00`, not `$0400` -- so `vicemon.Mon.screen_base` follows `$D018` and
  CIA2 `$DD00` rather than assuming the default and reporting stale memory.
* **Typing** is X11 XTEST into the VICE window.  NovaTerm scans the CIA1
  keyboard matrix itself and never reads the KERNAL buffer, so VICE's own
  `keybuf` monitor command reaches it not at all -- measured, by injecting `t`
  at the main menu and watching nothing happen.

The menu **remembers where it was left**, so nothing here counts keypresses
from an assumed top: every move reads the current selection first.  Assuming it
started at the top is how an early run walked into "Exit terminal / Are you
sure?".
"""
import time
from vicemon import Mon
from c64keys import Keys

# Main-menu items, in screen order, with the row each occupies.
MAIN_ROWS = range(9, 17)
MAIN_ITEMS = [
    "terminal mode", "dial a number", "configuration", "disk operations",
    "buffer menu", "device settings", "utility modules", "exit terminal",
]

class NovaTerm:
    def __init__(self, monport=29876):
        self.keys = Keys()
        self.keys.focus()
        self.monport = monport

    # ── reading ──────────────────────────────────────────────
    def _mon(self):
        return Mon(self.monport)

    def cells(self):
        """The 1000 raw screen codes, from wherever the VIC is really looking."""
        m = self._mon()
        v = m.peek(m.screen_base(), 1000)
        m.resume(); m.k.close()
        return v

    def text(self, v=None):
        """The screen as 25 lines of plain text."""
        v = v if v is not None else self.cells()
        def ch(c):
            c &= 0x7F
            if 1 <= c <= 26: return chr(ord('a') + c - 1)
            if c == 0x20 or c == 0x60: return ' '
            if 0x30 <= c <= 0x3F: return chr(c)
            if 0x21 <= c <= 0x2F: return chr(c)
            return '.'
        return ["".join(ch(v[r*40+c]) for c in range(40)).rstrip() for r in range(25)]

    def selected(self, rows=MAIN_ROWS):
        """Which menu row is highlighted.

        The selection is a wide reverse-video bar; an unselected row carries a
        single reversed cell, its hotkey letter.  Counting reversed cells tells
        them apart, where testing bit 7 alone does not -- the whole menu box is
        drawn reversed.
        """
        v = self.cells()
        best, best_n = None, 1
        for i, r in enumerate(rows):
            n = sum(1 for c in range(40) if v[r*40+c] & 0x80)
            if n > best_n:
                best, best_n = i, n
        return best

    # ── typing ───────────────────────────────────────────────
    def press(self, key, settle=0.35):
        self.keys.focus(); self.keys.key(key); time.sleep(settle)

    def type(self, s, settle=0.8):
        self.keys.focus(); self.keys.type(s); time.sleep(settle)

    def choose(self, name, rows=MAIN_ROWS, items=MAIN_ITEMS):
        """Move the highlight onto `name` and press RETURN."""
        want = items.index(name)
        here = self.selected(rows)
        if here is None:
            raise RuntimeError("no menu selection visible; is NovaTerm at a menu?")
        step = "Down" if want > here else "Up"
        for _ in range(abs(want - here)):
            self.press(step, 0.3)
        got = self.selected(rows)
        if got != want:
            raise RuntimeError("wanted %r (row %d), highlight is on row %d" % (name, want, got))
        self.press("Return", 1.5)
