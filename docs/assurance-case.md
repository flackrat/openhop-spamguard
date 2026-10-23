# Security assurance case

Why SpamGuard's security requirements are met: what it must protect, what could go wrong, how the design
deals with each risk, and the evidence that it does. Spam detection itself is left out on purpose; this is
about keeping SpamGuard, the repeater and the people on the mesh safe.

## 1. What SpamGuard must protect

1. **The repeater.** SpamGuard holds an openHop API token, so it can change openHop's rules. It must not let
   anyone else use that to disrupt the repeater.
2. **The mesh.** Its rules must only ever hold back spam and floods, never direct messages,
   acknowledgements or the repeater's own traffic, and they must expire by themselves.
3. **People's privacy.** It reads channel messages, so what it stores and shows must stay on the repeater,
   and nothing personal may reach the public repository.
4. **The software people install.** Releases must be what this repository built, unchanged.

## 2. Trust boundaries

1. **The radio network:** untrusted. Anyone can send any packet, including deliberately malformed ones.
2. **The local network:** partly trusted. The web page is reachable by devices on the same network as the
   repeater. The operator can protect changes with an access key.
3. **openHop:** trusted. SpamGuard talks to openHop's local API with the operator's token.
4. **GitHub:** trusted for code and releases, protected by the repository's rules and signed releases.

## 3. Threats and how each is met

| Threat | How it's met | Evidence |
|--------|--------------|----------|
| Malformed or hostile packets crash SpamGuard or make it misbehave | Every packet is parsed defensively with length checks, and decoding errors are caught per packet. Text is treated as data, never run. | Fuzz tests (`tests/testfuzz.py`, Atheris in `.github/workflows/fuzz.yml`), `tests/redteam.py` |
| Spam that gets SpamGuard to block genuine people | Rules are short-lived and narrow, people SpamGuard knows are let through, and the "possibly genuine" list shows anything held by mistake. | `tests/testfreespeech.py`, `tests/redteam.py` (fails if genuine messages are wrongly stopped) |
| Rules that harm the mesh | Rules only cover channel messages and flood packets, never direct messages, acknowledgements or the repeater's own traffic, and every rule has an expiry. | `tests/testown.py`, `tests/testfloodguard.py`, the rule list on the page |
| Someone on the network changing settings | An optional access key protects every change and the evidence download. Changes must be sent as JSON, so a web page elsewhere can't make someone's browser send them. | `tests/testsecrets.py` |
| Secrets leaking | The openHop token, the access key and channel keys never appear in the status, the rule list or the logs. | `tests/testsecrets.py`, `tests/testrulesview.py` |
| Personal details in the public repository | A privacy check with a private blocklist, Gitleaks and Presidio run on every pull request, and a pull request can't merge until they pass. | `tools/privacy_check.py`, `tests/testprivacy.py`, `.github/workflows/tests.yml` |
| A tampered or fake release | Releases are built only by the release workflow from `main`, virus-scanned, signed with Sigstore and a build attestation, published only once complete, and immutable after. Updates download only from this repository over HTTPS. | `.github/workflows/release.yml`, [SECURITY.md](../SECURITY.md) |
| A vulnerable dependency | Few dependencies, all pinned with hashes. Dependabot, pip-audit, dependency review and a weekly image scan watch them. | `requirements/`, `.github/workflows/audit.yml`, `.github/workflows/image-scan.yml` |
| A mistake in the workflows themselves | Every action is pinned to a commit, tokens are read-only by default, and zizmor checks the workflows. | `.github/workflows/audit.yml` |
| Weak cryptography | SpamGuard reads MeshCore channel messages with the encryption MeshCore defines (AES in ECB mode with a short HMAC), because that's the network's format. It never uses it to protect anything of its own. Its own connections use TLS 1.2 or newer with certificate checks, and random values come from the operating system. | `spamguard.py` (channel decoder, websocket connection) |

## 4. Secure design principles applied

1. **Least privilege:** SpamGuard needs no special rights of its own on the repeater. It only needs
   openHop's API token, it only changes rules it owns (named `spamguard:...`), and the few system commands
   it runs use fixed argument lists, never a shell.
2. **Fail safe:** if SpamGuard stops, its rules expire and the repeater carries on as normal. Monitor mode
   lets an operator see what it would do before it does anything.
3. **Economy of mechanism:** one Python program with two small dependencies, no database and no cloud.
4. **Complete mediation:** every change goes through one handler that checks the access key and the content
   type before anything else.
5. **Open design:** the code is public and its security doesn't rely on secrecy. Only the detail of spam
   detection is kept out of public documents, to avoid helping spammers, not for security.
6. **Separation of duties:** nobody can push to `main` or move a release tag directly; every change passes
   the required checks first.

## 5. Common weaknesses countered

| Weakness (CWE) | Counter |
|----------------|---------|
| Injection (CWE-77, 78, 94) | No shell is ever used and no command is built from received data; messages are only compared and stored. |
| Cross-site scripting (CWE-79) | The page escapes everything from the mesh before showing it. |
| Cross-site request forgery (CWE-352) | Changes require JSON and, when set, the access key. |
| Path traversal (CWE-22) | File names are fixed or generated; nothing from the mesh becomes a path. |
| Secrets in output (CWE-200, 532) | Tested: no secrets in status, rules or logs. |
| Insecure temporary files (CWE-377) | Temporary files go in private folders. |
| Unchecked input (CWE-20) | Packets are length-checked and fuzz-tested. Settings are checked against their allowed ranges. |

## 6. How this is kept true

CodeQL (extended security rules), Bandit, Ruff, pip-audit, zizmor, Gitleaks, the privacy check and the full
test suite run on every pull request or every week. A change that weakens any of the above has to get past
those checks and the maintainer's review. Security reports are handled as described in
[SECURITY.md](../SECURITY.md).
