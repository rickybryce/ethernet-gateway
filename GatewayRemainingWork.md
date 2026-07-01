# Gateway Master/Slave — Remaining Work

**Status as of 2026-07-01 (origin/dev `87a4486`):** the master/slave serial
extender is feature-complete and reviewed. Everything from the original
"later pile" has shipped **except one item that needs physical hardware to
verify** — the DCD/drive-carrier validation below. That is the only open
deferral, and it does not gate the 0.6.3 release.

Companion docs: `GatewaySlavePlan.md` (the design + resolved-issue log),
`README.md` (user docs + "Relay limitations" + "Outbound Connections").

---

## Open deferral — DCD / drive-carrier hardware validation

The `serial_X_drive_carrier` feature (DTR-as-DCD carrier proxy, commit
`3fd25f0`) is implemented, unit-tested on its decision logic and off-path, and
wired into all three UIs. What remains is **validation on real hardware**:
`socat` PTYs do not carry modem-control lines, so nothing in CI can confirm the
gateway actually toggles DTR the way `AT&C` specifies.

- **How:** the harness in **`tools/dcd-validate/`** (Option B — two USB-serial
  adapters, gateway DTR crossed to an observer's DCD/DSR/CTS input). Run
  `dcd_observer.py` on the observer adapter and drive calls on the gateway;
  confirm `&C1` follows the call, `&C0` forces carrier on, relay-link-loss
  drops it, and `drive_carrier = false` moves nothing (the safety guarantee).
- **Deferred sub-item:** an optional second config key to drive **RTS** instead
  of DTR was not built (DTR only for now). Add only if a target machine needs
  it — no known requirement today.

This is a manual bench check (same class as the CCGMS/VICE harnesses), to be
run when the hardware is on hand.

---

## Everything else is done or a decided non-goal

Shipped and reviewed this cycle (see `GatewaySlavePlan.md` and the CHANGELOG for
detail):

- Manual two-instance SSH smoke test — **run 2026-07-01** (found + fixed the
  relay-teardown panic `837632f`; all scenarios incl. #15 keepalive and the
  standalone regression passed).
- In-process through-relay transfer harness (`src/relay/tests.rs`) covering all
  five protocols over the onward-dial hop.
- Relay channel-open handshake / protocol version (#9), live relay-status
  observability (#10), through-relay interop (#11).
- Optional DTR-as-DCD carrier signalling (#2, code complete — see the open
  validation above).
- Serial administrative-broadcast channel (`serial::broadcast_to_serial`) and
  the transport-neutral shutdown-goodbye broadcast, completing broadcast
  coverage across telnet/SSH/relay/serial.

Decided **non-goals** (documented, not planned — rationale in
`GatewaySlavePlan.md` §4.3):

- **`relay_transport = raw`** — SSH is the adopted transport (auth + encryption +
  port reuse for free). A raw pipe would carry the identical bytes but needs a
  second open port and hand-rolled auth/lockout, with no encryption. The key is
  retained but hidden from the UIs and startup-warned if hand-set.
- **Head-of-line blocking in `ssh.rs data()`** — not reachable with today's
  one-channel-per-connection design; only relevant if a future single-connection
  multi-channel design lands.

---

(0.6.3 is still held — nothing here gates a release. When 0.6.3 ships, run the
`versionchange.txt` checklist.)
