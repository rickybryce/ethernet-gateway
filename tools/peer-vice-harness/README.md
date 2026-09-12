# Peer-to-peer transfer harness (two real C64s, through the relay)

Two Commodore 64s (NovaTerm 9.6c under VICE), one on a **slave** gateway and
one on the **master**, dial each other and move a file between themselves.  The
gateways are a *pipe* here — neither end is an endpoint of the transfer, which is
what makes this different from `../relay-vice-harness`, where the C64 talks to
the gateway's own file menu.

    C64 ── PTY ── SLAVE gateway ══ SSH relay ══ MASTER gateway ── PTY ── C64
    (141)         port A, modem                 port A, modem          (178)

The call is placed with `ATD <Port>@<host>`: a slave sees a non-local address,
relays it to the master, and the master resolves it to one of its own ports (or,
via the crossbar, to another slave's).  From then on the two C64s are talking to
each other and the gateways are carrying bytes.

## Layout

| Where | File | What it does |
|---|---|---|
| dev box | `run-peer.sh` | One transfer, slave's C64 → master's C64, end to end |
| dev box | `run-rev.sh` | The same in reverse, master's C64 → slave's C64 |
| both | `start-pty.sh` | The socat PTY pair: gateway holds `ttyGW`, VICE holds `ttyC64` |
| both | `start-vice.sh` | VICE + NovaTerm, **and drops out of warp and proves it** |
| both | `peer.py` | Terminal mode, dial, screen |
| both | `arm.py` | Re-arm auto-answer (see below) |
| both | `reset.py` | `C= Z` out of any transfer screen, terminal mode, hang up |
| both | `xfer.py` | Select a protocol; arm a receiver; start a sender |
| both | `linktest.py` | Prove the link carries bytes *both ways*, with no protocol involved |

The C64-driving machinery (`novaterm.py`, `c64keys.py`, `vicemon.py`,
`vicewarp.py`, `d64read.py`, `payloads/`) is **not duplicated** — copy it from
`../punter-vice-harness` and `../relay-vice-harness` onto both machines, as
those READMEs say.  Two copies of a screen-scraper drift, and the one that
drifts is the one you are not looking at.

## Setting up a second machine

VICE binaries are **not** portable between the two (one is x86_64, the other
aarch64) — install VICE from the distribution on each.  The **ROMs are data**
and Debian's package ships none, so copy `/usr/share/vice/{C64,DRIVES,PRINTER}`
from a machine that has them.  `python3-xlib` is required for the key injection.

Each gateway needs one port in **modem** mode pointing at its `run/ttyGW`, and
`allow_peer_dial = true` so a slave will relay a peer address to its master.

## Things measured the hard way

* **Boot under `-warp`, then drop to 1x and PROVE it.**  This harness's first
  runs had both emulators at **155 and 193 jiffies/sec** — 2.6x and 3.2x too
  fast — because `start-vice.sh` passed `-warp` and never took it back out.
  Punter handshaked and got nowhere, which reads as a protocol failure and is
  a speed problem.  `vicewarp.py` measures, toggles only if fast, and measures
  again; `start-vice.sh` now calls it.  A correct protocol on a machine running
  3x too fast is not a faster test, it is a broken one.

* **NovaTerm's own init string disables auto-answer.**  Entering terminal mode
  sends `...S0=0...`, which overrides whatever `serial_*_s_regs` says, so the
  answering side never picks up and the caller waits out the window.  `arm.py`
  re-sends `ATS0=1` **and reads `ATS0?` back** rather than assuming it took.

* **Prove the pipe before blaming the protocol.**  `linktest.py` puts both ends
  in terminal mode without hanging up and shows what each one received.  That is
  what ruled out a one-way link here: the receiver had `ack`s and the sender had
  `goo`s, so bytes crossed in both directions and the fault was elsewhere.

* **The `.d64` on the host lags the emulator.**  A file can read `0 blocks` and
  `*seq` (unclosed) on the host image while the transfer is still running, or
  even after it finished — `peerrecv` looked aborted and was complete.  Judge a
  run by **extracting the file and comparing bytes**, never by the directory
  listing, and never by a screen that may be showing scrollback.

* **The screen scraper can show you history.**  `novaterm.text()` returned a
  screen from two attempts earlier at one point.  When a verdict matters, take a
  picture of the window (`import -window root`) — the VICE status bar also shows
  warp state and CPU%, which is how the speed problem above was confirmed.

## Result

Verified 2026-09-12 between 192.168.1.141 (slave, Dell 6420) and 192.168.1.178
(master, Pi 5), payload `PUNTEST.SEQ`, 1775 bytes, compared by SHA-256:

| Direction | Protocol | Result |
|---|---|---|
| slave → master | Punter | identical |
| slave → master | XMODEM-CRC | identical |
| master → slave | XMODEM-CRC | identical |
