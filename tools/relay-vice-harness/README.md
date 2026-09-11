# Master/slave transfer harness (a real C64, over a relay)

Runs every transfer protocol the gateway speaks from a **real Commodore 64**
(NovaTerm 9.6c under VICE) that is talking to a **slave** gateway, against
files that live on the **master** — so what is under test is the relay, not a
loopback.  It is the `punter-vice-harness` matrix repeated one hop further out.

    C64 (VICE) ──serial PTY or tcpser/telnet──▶ SLAVE gateway ──SSH relay──▶ MASTER gateway
                                                                             (menu + files)

Only the pieces that are *new* for the relay live here.  The C64-driving
machinery — `novaterm.py`, `c64keys.py`, `vicemon.py`, `d64read.py`,
`verify-run.py`, `verify-upload.py`, `payloads/` — is shared with
`../punter-vice-harness` and is **not duplicated**: copy that directory onto
the slave alongside these files.  Two copies of a screen-scraper drift, and the
one that drifts is the one you are not looking at.

## Layout

| Where it runs | File | What it does |
|---|---|---|
| dev box | `relay-sweep.sh` | The sweep. Seeds the master, runs each cell on the slave, archives the evidence, and **grades the bytes** |
| slave | `relay-one.sh` | One protocol, one direction, against an already-running VICE |
| slave | `start-vice.sh` | VICE + NovaTerm for one link; restarted only when the link changes |
| slave | `start-slave.sh` | The slave gateway + its socat PTY pair (and the optional wiretap) |
| slave | `start-tcpser.sh` | The telnet link's virtual modem (shared with the punter harness) |
| slave | `run-transfer.py` | Drives NovaTerm through one transfer; `tg=host:port` adds the Telnet Gateway hop |
| slave | `freshdisk.py` | Swaps in a clean transfer disk without restarting the emulator |
| slave | `vicewarp.py` | Takes VICE out of warp, and **proves** it |
| slave | `step2.py`, `step-armonly.py` | Diagnostics: one cell with a screen after every keystroke, and a receiver armed with nothing on the other end |
| slave | `ptydial.py`, `ptymenu.py`, `tnprobe.py` | Probe the relay from a plain PTY, with no C64 in the way |
| slave | `slave.conf.sample` | The slave's config. **Fill in the credentials** — the sample carries placeholders |

## Running it

On the slave, once per link:

    ./start-slave.sh serial      # or telnet
    ./start-vice.sh   serial     # same word; the ACIA wiring differs

Then from the dev box:

    LINK=serial ./relay-sweep.sh xmodem:download xmodem:upload zmodem:download …

Results land in `results/<link>/` — the C64's own disk image, the screen, and
an exact slice of each gateway's log.  **Keep them somewhere that survives a
reboot**: an earlier run of this harness archived into a session scratchdir
under `/tmp` and lost a full 12-cell leg when the machine locked up.

## Things measured the hard way

* **A screen that says "complete" is not a result.** Every cell ends in a byte
  comparison against the payload, and a run with no output file fails however
  cheerful the screen was.
* **The instrument must not out-wait the product.** `run-transfer.py` ends a
  run when the screen stops changing; an *armed* receiver's screen is static by
  definition, and the gateway's negotiation window is 45 s, so the original
  40 s rule could call a run over before the product had either moved a byte or
  reported its own timeout.  `SETTLE_FLOOR` holds the verdict back.
* **A PTY pair never drops carrier.** socat holds both ends open, so a session
  that ended leaves the modem online and the next run types `ATDT` at a
  still-connected remote.  `relay-one.sh` restarts the slave for a clean line.
* **Ask the wire, not the parties.** `SOCAT_TRACE=1` wiretaps the PTY pair.
  When a transfer fails to start, "did the device transmit?" cannot be answered
  by the gateway (a suspect) or by NovaTerm (not answerable at all).
* **The emulated 1541 caches its directory.** Reformatting the image under a
  running drive is not the same as changing the disk: the image is clean
  immediately afterwards, and the drive can still write its *old* directory
  back over it.  Read the image after a run, not only before.
* `C=` is NovaTerm's **abort** key as well as its start key, and ZMODEM
  auto-downloads — so a blind start keystroke can cancel a transfer already in
  its data phase.  `run-transfer.py` asks the screen first; its comments carry
  the rest of these.
