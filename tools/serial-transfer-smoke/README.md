# Transfers to and from the gateway over a SERIAL link

Two harnesses already existed and neither covered this case:

* `tools/telnet-transfer-smoke` drives the product's own transfer menu, but
  only over **telnet**.
* `tools/peer-transfer-smoke` uses a **serial** link, but with the gateway as
  a **pipe** between two devices rather than as an endpoint.

This one dials the gateway's own menu over a serial wire with
`ATDT ethernetgateway` and transfers **to and from the gateway itself** — the
way a vintage machine on a cable actually reaches it.

## What it does not add

The peer is `lrzsz` (`sx`/`sz`/`rx`/`rz`/`sb`/`rb`) — the same implementation
the telnet harness and the `src/` protocol gates already use. So this harness
proves the **link and the product path**, not the protocol code, and it cannot
find the class of defect an independent implementation finds. Both real defects
in this area came from a *different* peer: NovaTerm's Punter exposed the RFC 856
BINARY refusal, and NovaTerm's YMODEM exposed a receiver framing one byte late.
`lrzsz` behaves like neither. Keep `tools/punter-vice-harness` for that job.

## Requirements

- `socat`, `lrzsz`, `python3`, a built gateway (`GATEWAY_BIN` overrides)

## Run

```sh
./run.sh                # every protocol, both directions
./run.sh zmodem         # just one
SIZE=32768 PORT=2398 ./run.sh
```

Exit 0 = every path matched byte for byte.

## The link

`socat` makes a PTY pair. The gateway opens one end as serial port A in modem
mode; the driver opens the other. **A PTY has no baud rate**, so transfers run
at host speed rather than at 2400 — which is why this is minutes rather than
the hours a real terminal under emulation takes.

To drive the same link by hand, `run.sh` prints the command:

```sh
minicom -D work/ttyUS -b 115200
```

Then `ATDT ethernetgateway`, and minicom's own Ctrl-A S / Ctrl-A R for
transfers — which shell out to the same `lrzsz` the driver uses.

## Two things that cost a run each

**The config key is `serial_a_port`, not `serial_a_device`.** An unknown key is
dropped silently, so the port simply had no device and the dial got no
`CONNECT` — with nothing in the log to say why. The gateway rewrites the file
with every key it knows, so `grep serial_a work/ethernetgateway-data/egateway.conf`
after a start shows what it actually read.

**A PTY pair never drops carrier.** `socat` holds both ends open, so a finished
session leaves the modem **online** and the next dial types `ATDT` at a remote
that is still connected. Every dial therefore begins with the `+++` escape —
with its guard-time silence either side, or the modem reads it as three data
bytes — then `ATH` and `ATZ`. On real hardware, unplugging does this for you.

## Reading the transport shim

`link.py` dresses a PTY as a socket (`recv`/`sendall`/`settimeout`/`fileno`)
so `driver.py` can substitute `telnet-transfer-smoke`'s `login()` and reuse its
menu navigation, `settle()` rule and lrzsz handoff **unchanged**. That is the
point of the design: two copies of the navigation would drift, and then a
difference between the links would read as a gateway defect. The PTY is forced
into raw mode — a cooked line discipline maps CR to LF and would corrupt every
block of every protocol, identically on each retry, past any CRC.
