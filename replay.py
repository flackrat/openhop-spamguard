#!/usr/bin/env python3
"""
SpamGuard replay: run a downloaded evidence log back through SpamGuard's detection with
different settings, and see what would have been caught, missed, or wrongly blocked.

Nothing touches openHop or the radio - it all happens on a simulated clock.

  python3 replay.py evidence.jsonl                      # compare relaxed / balanced / strict
  python3 replay.py evidence.jsonl --set dedupe_seconds=600 --set hop_new_senders=8
  python3 replay.py evidence.jsonl --sensitivity strict --details

On the Pi use openHop's Python:  /opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py ...

Your "This is spam" / "Not spam" answers in the log are treated as the truth. Messages you never
labelled are reported separately so you can check them by eye.
"""
from __future__ import annotations

import argparse
import logging
import hashlib
import hmac
import json
import os
import sys
import tempfile
import time as _real_time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spamguard as sg  # noqa: E402

try:
    from Crypto.Cipher import AES
except ImportError:
    sys.exit("pycryptodome is needed (use openHop's venv python on the Pi)")


class Clock:
    """Stands in for the time module so SpamGuard runs on log time."""
    now = 0.0

    def time(self):
        return Clock.now

    def __getattr__(self, name):
        return getattr(_real_time, name)


def encrypt(sender: str, text: str, key_hex: str) -> str:
    k = sg._secret32(key_hex)
    pt = b"\x00\x00\x00\x00\x00" + f"{sender}: {text}".encode()
    pt += b"\x00" * ((-len(pt)) % 16)
    ct = AES.new(k[:16], AES.MODE_ECB).encrypt(pt)
    return (bytes([sg.channel_hash_byte(key_hex)]) + hmac.new(k, ct, hashlib.sha256).digest()[:2] + ct).hex()


def load(path):
    msgs, labels, settings = [], {}, None
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            t = r.get("type")
            if t == "msg":
                msgs.append(r)
            elif t == "label":
                # match a label to a message by packet id, else by sender + text
                k = r.get("packet") or f"{r.get('sender')}|{r.get('text')}"
                labels[k] = r["label"]
            elif t == "settings" and settings is None:
                settings = r
    msgs.sort(key=lambda r: r["ts"])
    for m in msgs:
        m["_label"] = labels.get(m.get("packet")) or labels.get(f"{m['sender']}|{m['text']}")
    return msgs, labels, settings


def run(msgs, overrides: dict, channels: dict):
    sg.time = Clock()  # SpamGuard now runs on log time
    recorded = {m["sender"]: m.get("name_score", 0) for m in msgs}
    real_score = sg.name_score
    scrambled = all(m["sender"].startswith("N-") for m in msgs[:50]) if msgs else False
    if scrambled:
        # Names were scrambled: use the scores worked out on the Pi from the real names.
        sg.name_score = lambda name, pats: recorded.get(name, 0)
    state = tempfile.mktemp(suffix=".json")
    cfg = {"state_file": state, "evidence_log": False, "mode": "protect", **overrides}
    g = sg.SpamGuard(cfg)
    g.cfg["channels"].update(channels)
    keys = {name: key for name, key in g.cfg["channels"].items()}
    step = g.cfg["poll_seconds"]
    out = []
    i = 0
    Clock.now = msgs[0]["ts"] if msgs else 0
    end = (msgs[-1]["ts"] + 300) if msgs else 0
    while Clock.now <= end:
        batch = []
        while i < len(msgs) and msgs[i]["ts"] <= Clock.now:
            m = msgs[i]
            key = keys.get(m.get("channel") or "Public", sg.PUBLIC_CHANNEL_KEY)
            batch.append({"id": i, "timestamp": m["ts"], "type": sg.PAYLOAD_TYPE_GRP_TXT,
                          "payload": encrypt(m["sender"], m["text"], key), "packet_hash": f"r{i}",
                          "original_path": json.dumps(m.get("path") or [])})
            i += 1
        if batch:
            n = g.ingest(batch)  # (old events may be dropped from the front, so take the newest n)
            for e in (list(g.events)[-n:] if n else []):
                b = g.blocks.get(e.matched) if e.matched else None
                out.append((e.packet, e.matched, b.get("source") if b else None))
        g.decide()
        Clock.now += step
    sg.name_score = real_score
    try:
        os.remove(state)
    except OSError:
        pass
    caught = {pk: (key, src) for pk, key, src in out}
    return caught, g


def summarise(msgs, caught):
    res = {"total": len(msgs), "caught": 0, "spam": 0, "spam_caught": 0, "genuine": 0, "genuine_caught": 0,
           "by_source": {}, "missed": [], "wrong": [], "unlabelled_caught": []}
    for idx, m in enumerate(msgs):
        k, src = caught.get(f"r{idx}", (None, None))
        hit = k is not None
        res["caught"] += hit
        if hit:
            res["by_source"][src or "?"] = res["by_source"].get(src or "?", 0) + 1
        lab = m["_label"]
        if lab == "spam":
            res["spam"] += 1
            res["spam_caught"] += hit
            if not hit:
                res["missed"].append(m)
        elif lab == "not_spam":
            res["genuine"] += 1
            res["genuine_caught"] += hit
            if hit:
                res["wrong"].append(m)
        elif hit:
            res["unlabelled_caught"].append(m)
    return res


def line(m):
    t = _real_time.strftime("%d %b %H:%M", _real_time.localtime(m["ts"]))
    return f"  {t}  {'>'.join(m.get('path') or []) or 'direct':<18} {m['sender'][:16]:<16} {m['text'][:70]}"


def main():
    ap = argparse.ArgumentParser(description="Replay a SpamGuard evidence log with different settings")
    ap.add_argument("log", nargs="+", help="evidence .jsonl file(s)")
    ap.add_argument("--sensitivity", choices=sorted(sg.PRESETS), help="replay one sensitivity only")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a setting")
    ap.add_argument("--hashtag", action="append", default=[], help="extra #channel to decrypt")
    ap.add_argument("--details", action="store_true", help="list missed, wrongly blocked and unlabelled catches")
    a = ap.parse_args()
    logging.disable(logging.WARNING)  # keep the report readable

    msgs, labels = [], {}
    for p in a.log:
        m, l, _ = load(p)
        msgs += m
        labels.update(l)
    msgs.sort(key=lambda r: r["ts"])
    if not msgs:
        sys.exit("No messages in the log. Is the evidence log switched on?")
    overrides = {}
    for kv in a.set:
        k, _, v = kv.partition("=")
        overrides[k] = json.loads(v) if v[:1] in "0123456789-[{tfn" else v
    channels = {t if t.startswith("#") else "#" + t: sg.hashtag_secret(t) for t in a.hashtag}
    for ch in {m.get("channel") for m in msgs}:
        if ch and ch.startswith("#"):
            channels.setdefault(ch, sg.hashtag_secret(ch))

    days = (msgs[-1]["ts"] - msgs[0]["ts"]) / 86400
    nspam = sum(1 for m in msgs if m["_label"] == "spam")
    ngen = sum(1 for m in msgs if m["_label"] == "not_spam")
    print(f"{len(msgs)} channel messages over {days:.1f} days; you labelled {nspam} as spam and {ngen} as genuine.")
    orig = sum(1 for m in msgs if m.get("caught_by"))
    print(f"Originally caught on the Pi: {orig}\n")

    runs = [a.sensitivity] if a.sensitivity else ["relaxed", "balanced", "strict"]
    print(f"{'Settings':<34}{'Caught':>8}{'Spam caught':>14}{'Genuine blocked':>17}")
    results = []
    for sens in runs:
        ov = dict(overrides, sensitivity=sens)
        caught, _ = run(msgs, ov, channels)
        r = summarise(msgs, caught)
        results.append((sens, r))
        label = sens + (" + " + ", ".join(a.set) if a.set else "")
        sc = f"{r['spam_caught']}/{r['spam']}" if r["spam"] else "-"
        gc = f"{r['genuine_caught']}/{r['genuine']}" if r["genuine"] else "-"
        print(f"{label[:33]:<34}{r['caught']:>8}{sc:>14}{gc:>17}")
    print()
    for sens, r in results:
        print(f"[{sens}] caught by: " + ", ".join(f"{k} {v}" for k, v in sorted(r["by_source"].items())) or "nothing")
    if a.details:
        for sens, r in results:
            print(f"\n=== {sens} ===")
            if r["missed"]:
                print(f"Labelled spam that got through ({len(r['missed'])}):")
                for m in r["missed"][:40]:
                    print(line(m))
            if r["wrong"]:
                print(f"Labelled genuine but blocked ({len(r['wrong'])}):")
                for m in r["wrong"][:40]:
                    print(line(m))
            if r["unlabelled_caught"]:
                print(f"Caught but not labelled - check these ({len(r['unlabelled_caught'])}):")
                for m in r["unlabelled_caught"][:40]:
                    print(line(m))


if __name__ == "__main__":
    main()
