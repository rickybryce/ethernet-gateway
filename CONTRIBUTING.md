# Contributing to Ethernet Gateway

Thanks for looking. This is a small project with one maintainer, so the fastest
route for anything non-trivial is to **open an issue before writing code** —
much of this codebase is shaped by behaviour measured against real hardware,
and the reason a thing is the way it is often isn't visible from the source.

- **Bugs and features:** open a
  [GitHub issue](https://github.com/rickybryce/ethernetgateway/issues).
- **Security vulnerabilities:** do **not** open an issue. Follow
  [`SECURITY.md`](SECURITY.md).
- **Code:** open a pull request against `master`.

By contributing you agree your work is licensed under **GPL-3.0-or-later**, the
same terms as the project ([`LICENSE`](LICENSE)).

## Building and testing

```sh
cargo build                      # debug build
cargo build --release            # release build
cargo test                       # the whole suite
cargo clippy --all-targets       # lints
```

The **minimum supported Rust version is 1.92**, and CI has a job that enforces
it. Don't read the MSRV off our own source — it is the highest `rust-version`
in the entire dependency graph, and ours is usually not the one that wins.
Measure it:

```sh
cargo metadata --format-version 1 | python3 -c "import json,sys; \
  print(max((p['rust_version'] for p in json.load(sys.stdin)['packages'] \
  if p.get('rust_version')), key=lambda v: tuple(map(int, v.split('.')))))"
```

CI builds on Linux, macOS and Windows with the **latest stable** rustc, and the
repo pins no toolchain — so a local compiler behind current stable can pass
locally and fail CI on a newly-added lint. Run `rustup update stable` before
proposing anything large.

## What a contribution has to satisfy

**The gates are `cargo build`, `cargo clippy` and `cargo test`.** CI runs the
first two with `-D warnings`, and all three must be clean.

**Do not run `cargo fmt`.** This codebase is deliberately hand-formatted and
has never been rustfmt-formatted. Measured on the current tree, `cargo fmt
--check` disagrees with it at **3139 locations across 77 of the 79 `.rs`
files** — so a single run rewrites essentially the whole codebase and flattens
alignment that is there on purpose. CI's `rustfmt` job is advisory
(`continue-on-error`) and never gates a build. Match the formatting of the code
around your change.

Beyond that, three rules carry most of the review feedback here:

**1. Measure; don't reason.** This project talks to 1970s and 1980s hardware,
and the recurring lesson is that a careful argument about how a device behaves
loses to a measurement every time. Disk geometries, printer line-feed
behaviour, joystick centre values, terminal escape handling and protocol
framing are all measured — usually by running period software and comparing
byte for byte — and the module comments say so. If you change one of those,
measure it the same way. A plausible model that is wrong survives review; a
byte-exact comparison does not.

**2. Protocol implementations are clean-room.** Punter, Kermit, ZMODEM, the
RomWBW HBIOS interface, the CP/M disk formats and EGT8080 are written from
published specifications. Another implementation's source may be used as a
*cross-check*, never as the source of truth — and note that a real
implementation's comments can be wrong: a mislabelled comment in a reference
codec's own test file was our oracle for two releases and cost a defect in
shipped code. Do not transcribe code from other projects.

**3. Don't hand-edit generated files.** `EGT8080/EGT8080.Z80` is derived from
`EGT8080/EGT80.Z80` by `EGT8080/tools/port8080.py` (`make port`, run from
`EGT8080/`) — edit the Z80 source, never the generated 8080 file. The
`.COM` binaries are built by a period assembler that **CI cannot run**, so if
you change the assembly you must rebuild them locally and commit the result
(see `EGT8080/README.md`).

## Tests

**New functionality must come with tests.** If your change adds behaviour, add
automated coverage for it to the suite; if it fixes a defect, add the test that
would have caught it. Pull requests without tests for new behaviour will be
asked for them.

Two further rules are worth knowing, because both were learned the hard way:

- **A test that cannot go red is worse than no test.** A test asserting a
  function's own postcondition, or scanning for a payload as a subsequence, or
  passing in 0.00s because an environment gate made it return early, provides
  false confidence. Where a test asserts something is *absent*, include a
  positive control proving the check could have seen it.
- **Mutate a new test before believing it.** Break the code the test is meant
  to guard, confirm the test fails, then restore. This has repeatedly caught
  tests in this repo that passed with the defect deliberately put back —
  including a 40-column width guard that asserted a function's own
  postcondition, and two interop gates that spent an unknown period passing
  without running.

Tests requiring external tooling or hardware (lrzsz, C-Kermit, a real CP/M
disk, a Commodore emulator) are marked `#[ignore]` and are run deliberately —
never gated behind an environment check that silently returns success, since
that reads as a pass while doing nothing.

## Documentation

Several settings are described on three surfaces — telnet, web and desktop —
plus the user manual. Prose beside a code-rendered list is the half that rots,
so some documentation is under test: `usermanual.html`'s Key/Default tables are
compared against a config written from `Config::default()`. If you add or
change a config key, update all the surfaces and expect a test to tell you when
you have missed one.

## Commit messages

Explain **why**, not just what. Where a change rests on something measured, put
the measurement in the message — those messages are the project's record of how
a behaviour was established, and they get read years later.
