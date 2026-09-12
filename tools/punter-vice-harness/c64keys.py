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
    # X11 keysyms are NAMED, not spelled: `string_to_keysym('.')` is NoSymbol.
    # The lookup then yielded keycode 0, and pressing keycode 0 types nothing
    # and raises nothing -- so every '.', ':', '-' and '/' typed at the C64
    # vanished in silence.  Measured consequences: `192.168.1.178` reached a
    # Host prompt as `1921681178` (the gateway dutifully tried to connect to
    # it), and `xmodemup.seq` reached a Filename prompt as `xmodemupseq` --
    # which was read as the gateway's validate_filename stripping the dot.  It
    # was not; the dot never left this file.  novaterm.py's `inst_del` carries
    # the same lesson for control characters.
    NAMES = {
        ' ': 'space',   '\n': 'Return', '\t': 'Tab',
        '.': 'period',  ',': 'comma',   ':': 'colon',     ';': 'semicolon',
        '/': 'slash',   '-': 'minus',   '_': 'underscore', '=': 'equal',
        '+': 'plus',    '*': 'asterisk', '?': 'question',  '!': 'exclam',
        '(': 'parenleft', ')': 'parenright', '@': 'at',    '#': 'numbersign',
        '$': 'dollar',  '%': 'percent', '&': 'ampersand',  "'": 'apostrophe',
        '"': 'quotedbl', '<': 'less',   '>': 'greater',    '\\': 'backslash',
    }

    def _resolve(self, ch):
        """Keycode for `ch`, and whether SHIFT is needed to reach it.

        A keycode carries several symbols by level, so pressing the keycode
        alone gives the UNSHIFTED one: asking for ':' and typing ';' is the
        same silent-substitution class as the missing keysym above, one layer
        down.  Ask the map which level actually matched.
        """
        ks = XK.string_to_keysym(self.NAMES.get(ch, ch))
        if ks == 0:
            raise KeyError("no X keysym for %r -- add it to Keys.NAMES" % ch)
        kc = self.d.keysym_to_keycode(ks)
        if kc == 0:
            raise KeyError("keysym %r is not on this keyboard layout" % ch)
        if self.d.keycode_to_keysym(kc, 0) == ks:
            return kc, False
        # It is not the unshifted symbol, so SHIFT is about to be pressed --
        # check that shifted is actually where it lives.  On a layout that puts
        # it at an AltGr level, pressing Shift reaches a DIFFERENT character and
        # types it with no error: the same silent substitution this whole table
        # exists to stop, one level further down.
        if self.d.keycode_to_keysym(kc, 1) != ks:
            raise KeyError(
                "%r is on keycode %d but at neither level 0 nor 1 -- this "
                "layout would type something else" % (ch, kc)
            )
        return kc, True

    def key(self, ch, hold=0.05):
        kc, shift = self._resolve(ch)
        sk = self.d.keysym_to_keycode(XK.string_to_keysym('Shift_L')) if shift else None
        if sk:
            xtest.fake_input(self.d, X.KeyPress, sk); self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyPress, kc)
        self.d.sync(); time.sleep(hold)
        xtest.fake_input(self.d, X.KeyRelease, kc)
        self.d.sync(); time.sleep(hold)
        if sk:
            xtest.fake_input(self.d, X.KeyRelease, sk); self.d.sync(); time.sleep(hold)

    def type(self, s, gap=0.12):
        for ch in s:
            self.key(ch)
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
