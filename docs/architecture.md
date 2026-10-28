# How SpamGuard is built

A high-level picture of SpamGuard's parts and how they fit together. It describes the structure, not the
detail of how spam is recognised, which is kept out of public documents on purpose.

## The big picture

```
              MeshCore radio network
                       │
              ┌────────┴────────┐
              │  openHop        │  the repeater software: receives, decides, re-sends
              │  ┌───────────┐  │
              │  │ rule      │◄─┼──── rules written by SpamGuard (allow / drop / log only)
              │  │ engine    │  │
              │  └───────────┘  │
              └──┬───────────┬──┘
     packets and │           │ packet feed (websocket) and
     radio stats │           │ local API, with an API token
              ┌──┴───────────┴──┐
              │  SpamGuard      │  one Python program (spamguard.py)
              │  (+ FloodGuard) │
              └──┬───────────┬──┘
                 │           │
        web page │           │ state file and optional evidence log, on the repeater's own disk
       (port 8091)           │
```

SpamGuard never sends or forwards radio packets itself. It watches what openHop hears and tells openHop's
own rule engine what to stop. If SpamGuard stops, openHop carries on with the last rules it was given, and
those rules expire by themselves.

## The parts

1. **Collector.** Reads new packets from openHop's live feed, with a timed check as a backup, and decrypts
   the channel messages on the channels it has been given, using the channel keys openHop already holds. It also counts flooded requests, anonymous requests and
   group data by the kind of packet, the first repeater and the time, without opening them. When the optional
   signed-message setting is on, it also reads the trailer at the end of a decrypted channel message (as bytes), checks the
   Ed25519 signature against a key learnt from an advert, and keeps only counts and short key ids.
2. **Analysis.** Looks at recent channel traffic and decides what looks like spam. It also notices a route, or a
   flood of non-text packets through one repeater (or a few that together carry nearly all of it), that suddenly stands out, and suggests a time-limited block
   (it applies one itself only if the operator turned that on). It keeps short-lived
   records (recent messages, names it has learnt are genuine, routes) in memory and in the state file.
3. **Rules.** Turns each decision into an openHop rule with a lifetime, writes the full set to openHop's
   policy API, and checks openHop really applied them. Every rule SpamGuard owns is named `spamguard:...`
   so it never touches the operator's own rules.
4. **FloodGuard.** Measures how busy the radio is from the packets openHop reports, learns what's normal for
   the site, and adds hop limits when the radio is flooded. It also watches the noise floor for interference.
5. **Web page.** A single page (`ui.html`) served by SpamGuard's built-in web server. It reads one status
   endpoint and sends changes as JSON. The message list (Messages) is asked for separately, as JSON, because
   it can hold up to 7 days of channel messages. An optional access key protects every change, the message
   list and the evidence download.
6. **Evidence log.** Optional daily files of what SpamGuard saw and did, for checking its decisions, for the
   7-day message list, and for the replay tool (`replay.py`), which re-runs a log with different settings.
   Once a day SpamGuard runs the replay itself, at the lowest priority, to show what each protection level
   would have held.
7. **Updates.** An optional check against this repository's releases. An update downloads the release file
   over HTTPS from this repository only. The files are also signed, so anyone can check them by hand (see
   [SECURITY.md](../SECURITY.md)).

## How it's packaged

1. **openHop plugin** (the normal install): a wheel built by `tools/build_plugin.py`, installed from openHop's
   dashboard. openHop starts and stops SpamGuard and passes it its settings.
2. **Docker image:** the same program in a small container next to openHop.
3. **Older direct install:** a systemd service, kept for existing installs and moved to the plugin when the
   operator chooses.

## Where to look in the code

| Area | Where |
|------|-------|
| Settings, defaults and their help text | `SETTINGS_META` and `DEFAULT_CONFIG` near the top of `spamguard.py` |
| Packet collection and decryption | `SpamGuard.ingest` and the channel decoder |
| Rules written to openHop | `SpamGuard.build_rules` and the policy calls to `/api/policy` |
| FloodGuard | the `fg_*` methods |
| Web server and its endpoints | `make_handler` |
| Page | `ui.html` |
| Tests | `tests/` (run with `bash tests/run_all.sh`) |
