# Gateway Master/Slave — Remaining Work

**Status as of 2026-07-02 (origin/dev `88a2780`):** the master/slave serial
extender is feature-complete and reviewed, and the **peer-dial** feature
(call another serial port directly) has shipped through Phase 2. The open items
are two bench validations that need physical/second-host hardware, a small set
of peer-dial review follow-ups, and the 0.6.3 release. None gates day-to-day use.

Companion docs: `GatewaySlavePlan.md` (relay design + resolved-issue log),
`GatewayPeerDialPlan.md` (peer-dial design + status; untracked working doc),
`README.md` (user docs + "Peer-Dial" + "Relay limitations").

---

## Open — peer-dial review follow-ups (Phase 2b sweep, 2026-07-02)

Peer-dial Phase 1 (local) + Phase 2 (cross-gateway) shipped
(`363619d`/`851cbb5`/`a6a8f00`/`88a2780`). A 3-agent quality/stability/consistency
sweep found **no P1**; the committed code is green (1290 tests, clippy clean).
Follow-ups to apply (detail in `GatewayPeerDialPlan.md`):

- **P2 (bounded) — announcer `join()` stall on config restart.** The modem-port
  announcer's ring-wait (`request_peer_call`, 30s) isn't abort-aware, so a
  `SERIAL_RESTART` during it can delay that port's manager reopen up to ~30s in a
  narrow window. Bounded, self-clearing; process shutdown unaffected. Fix: make
  the announcer's ring-wait short-circuit on the shutdown/restart flag.
- **P2 (design decision) — modem port shares the console registry namespace.**
  A slave modem port announces via `serial-register <label>`, so it also appears
  in the master's Serial Gateway *picker* as a generic remote port (picking it
  rings the modem). Decide whether that menu-pickability is wanted (leave as-is)
  or the registration should carry a port-mode tag so the picker can label/filter.
- **P3 (cosmetic):** four stale doc-comments from the 2a→2b transition
  (`handle_peer_dial`, `handle_dial` slave path, `run_master_relay_peer`,
  `connect_master_register`); announcer connect-error `{:?}`→Display; the `30s`
  ring-wait literal duplicates `RELAY_PEER_ANSWER_WAIT`.

## Open — two-machine peer-dial live validation

Cross-gateway peer-dial (Phase 2a/2b) is addressed **by IP**, so it can't be
validated on a single host (master and slave would share `127.0.0.1`, and the
slave treats the master's address as local). It is unit-tested and the
master-side bridge is already live-proven by Phase 1 (`tools/peer-dial-smoke/`,
10/10 modem + 3/3 console). End-to-end confirmation wants **two machines** (or
two netns with distinct IPs): from a slave device dial `<Port>@<master-ip>` and
`<Port>@<other-slave-ip>` (console = direct, modem = rings).

---

## Open — DCD / drive-carrier hardware validation

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
- **Peer-dial** (`allow_peer_dial`): a modem port dials another port directly
  (`ATD <Port>@<IP>`) — Phase 1 (local, live-validated) + Phase 2 (cross-gateway
  over the relay: slave device → master port, and the master crossbar to any
  port a slave registers — console = direct, modem = rings). See the follow-ups
  and two-machine validation above.

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

## Release

0.6.3 is still held (`master` = `f39d178`). A large cycle has shipped on `dev`:
master/slave relay extender, serial broadcast, DCD carrier proxy, and peer-dial
Phase 1 + 2. When ready to release, run the `versionchange.txt` checklist, tag
`v0.6.3`, and fast-forward `master`. The open items above (peer-dial follow-ups,
the two bench validations) do not block a release, but the bench validations are
worth doing first if the hardware / second host is available.
