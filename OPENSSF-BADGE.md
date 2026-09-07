# OpenSSF Best Practices badge — prepared answers (passing level)

Working notes for the self-assessment at
<https://www.bestpractices.dev>. The questionnaire is **67 criteria** at
passing level (43 MUST, 10 SHOULD, 14 SUGGESTED), answered by the maintainer
under their own GitHub login — there is no write API, so this file exists to
make filling the form mechanical rather than to replace it.

Kept in the repository because the *justifications* are the valuable part: when
the badge is renewed, or a criterion changes, the reasoning behind each answer
is here rather than being reconstructed.

**One criterion is not a clean "Met" — see `crypto_password_storage` below.
Read that before submitting.** Everything else is either straightforwardly met
or legitimately N/A.

Repository: <https://github.com/rickybryce/ethernetgateway>

---

## Basics

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `description_good` | MUST | Met | `README.md` opens with what the software is and does. |
| `interact` | MUST | Met | README links issues, `CONTRIBUTING.md` and `SECURITY.md`. |
| `contribution` | MUST | Met | `CONTRIBUTING.md` — how to build, the gates, PR process. URL: `.../blob/master/CONTRIBUTING.md` |
| `contribution_requirements` | SHOULD | Met | Same file, "What a contribution has to satisfy" — gates, the `cargo fmt` prohibition, clean-room rule. |
| `floss_license` | MUST | Met | GPL-3.0-or-later. |
| `floss_license_osi` | SUGGESTED | Met | GPL-3.0 is OSI-approved. |
| `license_location` | MUST | Met | `LICENSE` at repo root, verbatim GPL-3.0 (sha256 `3972dc97…`, matches gnu.org). |
| `documentation_basics` | MUST | Met | `README.md` plus `usermanual.html`/`usermanual.pdf` and the reference pages under `web/`. |
| `documentation_interface` | MUST | Met | The user manual documents every config key and menu; its Key/Default tables are under test against `Config::default()`. |
| `sites_https` | MUST | Met | Repository and releases served over HTTPS by GitHub. |
| `discussion` | MUST | Met | GitHub Issues enabled. |
| `english` | SHOULD | Met | All documentation is in English. |
| `maintained` | MUST | Met | Actively maintained; Scorecard measured 30 commits in the last 90 days. |

## Change control

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `repo_public` | MUST | Met | Public Git repository on GitHub. |
| `repo_track` | MUST | Met | Git. |
| `repo_interim` | MUST | Met | Work lands on `dev` and `master` continuously between releases. |
| `repo_distributed` | SUGGESTED | Met | Git is distributed. |
| `version_unique` | MUST | Met | `Cargo.toml` version; every release is uniquely numbered. |
| `version_semver` | SUGGESTED | Met | Semantic versioning (e.g. `1.0.0-RC1`). |
| `version_tags` | SUGGESTED | Met | Releases are tagged `vX.Y.Z`. |
| `release_notes` | MUST | Met | `CHANGELOG.md` plus per-release GitHub release notes. |
| `release_notes_vulns` | MUST | Met | Security-relevant fixes are described in the changelog and commit messages. |

## Reporting

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `report_process` | MUST | Met | `CONTRIBUTING.md` says to open an issue; `SECURITY.md` covers vulnerabilities. |
| `report_tracker` | SHOULD | Met | GitHub Issues. |
| `report_responses` | MUST | Met | Issues are responded to by the maintainer. |
| `enhancement_responses` | SHOULD | Met | Enhancement requests are answered, including declining with a reason. |
| `report_archive` | MUST | Met | GitHub Issues is a public, permanent archive. URL: `.../issues` |
| `vulnerability_report_process` | MUST | Met | `SECURITY.md`. URL: `.../blob/master/SECURITY.md` |
| `vulnerability_report_private` | MUST | Met | `SECURITY.md` gives a private channel (not the public tracker). |
| `vulnerability_report_response` | MUST | Met | No report has gone unanswered. |

## Quality

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `build` | MUST | Met | `cargo build`. |
| `build_common_tools` | SUGGESTED | Met | Cargo, the standard Rust toolchain. |
| `build_floss_tools` | SHOULD | Met | Rust and Cargo are FLOSS. |
| `test` | MUST | Met | 2522 automated tests plus a binary end-to-end test. |
| `test_invocation` | SHOULD | Met | `cargo test`, documented in `CONTRIBUTING.md`. |
| `test_most` | SUGGESTED | Met | Coverage spans every protocol, the config parser, the CP/M emulator and the UI layout constraints. |
| `test_continuous_integration` | SUGGESTED | Met | GitHub Actions on every push and PR, three operating systems, plus a weekly scheduled run. |
| `test_policy` | MUST | Met | `CONTRIBUTING.md` § Tests: "New functionality must come with tests." |
| `tests_are_added` | MUST | Met | Practice matches the policy — recent example: `test_a_client_can_open_a_session_channel` added with the russh 0.62 change. |
| `tests_documented_added` | SUGGESTED | Met | `CONTRIBUTING.md` states it, including the rules that a test must be able to fail and should be mutation-checked. |
| `warnings` | MUST | Met | `cargo clippy`, and `RUSTFLAGS: -D warnings` in CI. |
| `warnings_fixed` | MUST | Met | CI runs build and clippy with `-D warnings`; a warning is a failure. |
| `warnings_strict` | SUGGESTED | Met | `-D warnings` is maximally strict for this toolchain. |

## Security

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `know_secure_design` | MUST | Met | Maintainer assertion. |
| `know_common_errors` | MUST | Met | Maintainer assertion. |
| `crypto_published` | MUST | Met | Ed25519, RSA and the SSH transport ciphers, via `russh`; no in-house cryptography. |
| `crypto_call` | SHOULD | Met | All cryptography is delegated to `russh` / RustCrypto; none is implemented here. |
| `crypto_floss` | MUST | Met | `russh` and RustCrypto are FLOSS. |
| `crypto_keylength` | MUST | Met | Ed25519 host keys (256-bit) generated by default. |
| `crypto_working` | MUST | Met | No broken primitives; SSH transport is negotiated by `russh`. |
| `crypto_weaknesses` | SHOULD | Met | No MD5/SHA-1 in a security role. |
| `crypto_pfs` | SHOULD | Met | SSH key exchange provides forward secrecy. |
| **`crypto_password_storage`** | **MUST** | **See note below** | **Not a clean Met — read the note before answering.** |
| `crypto_random` | MUST | Met | `rand::rng()` (OS CSPRNG) for key generation. |
| `delivery_mitm` | MUST | Met | Releases are downloaded over HTTPS from GitHub. |
| `delivery_unsigned` | MUST | Met | Every release artifact carries a cosign signature (`.sig`), certificate (`.pem`) and `.sha256`. |
| `vulnerabilities_fixed_60_days` | MUST | Met | Nine `russh` advisories (two HIGH) were fixed the day they were identified, in `977ff64`. |
| `vulnerabilities_critical_fixed` | SHOULD | Met | As above. |
| `no_leaked_credentials` | MUST | Met | No credentials in the repository. The `Config` type has a redacting `Debug` so a stray format cannot log one, guarded by a test. |

## Analysis

| Criterion | Cat | Answer | Justification |
|---|---|---|---|
| `static_analysis` | MUST | Met | CodeQL on every push and PR (`.github/workflows/codeql.yml`), plus `cargo clippy` with `-D warnings`, `cargo audit` and `cargo deny`. |
| `static_analysis_common_vulnerabilities` | SUGGESTED | Met | CodeQL's security queries. |
| `static_analysis_fixed` | MUST | Met | CodeQL alerts stand at zero; the 38 reported were fixed or dismissed with recorded reasons. |
| `static_analysis_often` | SUGGESTED | Met | Every push and PR, plus weekly. |
| `dynamic_analysis` | SUGGESTED | Met | Property-based tests (proptest) across the wire parsers, re-run at 4096 cases per property in CI; plus live protocol testing against real hardware and emulators. |
| `dynamic_analysis_unsafe` | SUGGESTED | N/A | Safe Rust; no memory-unsafety analysis tool applies in the sense meant. |
| `dynamic_analysis_enable_assertions` | SUGGESTED | Met | The debug profile panics on integer overflow, and the suite runs under it. |
| `dynamic_analysis_fixed` | MUST | Met | No outstanding findings. |

---

## The one to decide: `crypto_password_storage`

> *If the software produced by the project causes the storing of passwords for
> authentication of external users, the passwords MUST be stored as iterated
> hashes with a per-user salt by using a key stretching (iterated) algorithm
> (e.g., Argon2id, Bcrypt, Scrypt, or PBKDF2).*

**What we actually do.** `egateway.conf` holds `username` and `password` in
cleartext. Inbound telnet, SSH and web logins compare against them with
`telnet::constant_time_eq` (`src/telnet/session.rs:604`). There is no user
database and no per-user account — one operator-configured shared credential,
in a file on the operator's own machine, which the operator wrote.

**The argument for N/A**, which is the answer most appliance-shaped projects
give: the criterion targets storing *other people's* passwords. There are no
external user accounts here; there is one shared secret, and the party who set
it is the party who can read the file.

**The argument for Unmet**, which is not unreasonable: the software does
authenticate remote clients against a stored password, and that password is
stored in cleartext. Nothing about the comparison requires cleartext — an
iterated hash would work for the inbound credential, since we only ever need to
*verify* it.

**If we wanted to fix it rather than justify it**, the scope is not uniform:

- `username` / `password` (inbound telnet, SSH, web) — hashable. We only
  verify these.
- `slave_master_password` — **not** hashable. The slave presents this to the
  master, so it must be recoverable.
- `groq_api_key` — not a password; it is a bearer token that must be sent.

So a fix would cover the inbound credential only, and would change the config
format (a breaking change for existing installations, or a migration).

**Recommendation:** answer **N/A** with the justification above — it is honest
and it is what the criterion means — and treat hashing the inbound credential
as a separate design decision on its own merits, not as badge compliance.
Do not answer "Met": we do not hash anything today, and claiming otherwise
would be false.
