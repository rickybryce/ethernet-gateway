"""Type at VICE the way a person does: X11 synthetic keys into its window.

NovaTerm scans the CIA1 keyboard matrix itself and never looks at the KERNAL
buffer, so VICE's own `keybuf` monitor command reaches it not at all -- proved
by injecting `t` at its main menu and watching nothing change.  Going in at the
X level makes VICE build real matrix state, which is the only thing NovaTerm
will read.
"""
import time
from Xlib import display, X, XK
from Xlib.ext import xtest

class Keys:
    def __init__(self, disp=":0", title="VICE (C64SC)"):
        self.d = display.Display(disp)
        self.win = self._find(self.d.screen().root, title)
        if self.win is None:
            raise SystemExit("VICE window %r not found" % title)
    def _find(self, w, title, depth=0):
        try:
            if w.get_wm_name() and title in str(w.get_wm_name()):
                return w
        except Exception:
            pass
        if depth > 3:
            return None
        for c in w.query_tree().children:
            r = self._find(c, title, depth + 1)
            if r is not None:
                return r
        return None
    def focus(self):
        self.win.set_input_focus(X.RevertToParent, X.CurrentTime)
        self.d.sync(); time.sleep(0.2)
    def key(self, ch, hold=0.05):
        ks = XK.string_to_keysym(ch)
        kc = self.d.keysym_to_keycode(ks)
        xtest.fake_input(self.d, X.KeyPress, kc)
        self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyRelease, kc)
        self.d.sync(); time.sleep(hold)
    def type(self, s, gap=0.12):
        for ch in s:
            self.key({' ': 'space', '\n': 'Return'}.get(ch, ch))
            time.sleep(gap)

    def combo(self, mod, ch, hold=0.06):
        """A modified keypress, e.g. the C64 Commodore key plus a letter."""
        import time
        from Xlib import X, XK
        mk = self.d.keysym_to_keycode(XK.string_to_keysym(mod))
        kc = self.d.keysym_to_keycode(XK.string_to_keysym(ch))
        xtest.fake_input(self.d, X.KeyPress, mk); self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyPress, kc); self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyRelease, kc); self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyRelease, mk); self.d.sync(); time.sleep(hold)
