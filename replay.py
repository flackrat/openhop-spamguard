#!/usr/bin/env python3
"""
SpamGuard replay: run a downloaded evidence log back through SpamGuard's detection with
different settings, and see what would have been caught, missed, or wrongly blocked.

Nothing touches openHop or the radio - it all happens on a simulated clock.

  python3 replay.py evidence.jsonl                      # compare relaxed / balanced / strict
  python3 replay.py evidence.jsonl --set dedupe_seconds=600 --set hop_new_senders=8
  python3 replay.py evidence.jsonl --sensitivity strict --details
  python3 replay.py evidence.jsonl --levels 0,50,80,100 # protection levels instead of the three presets

On the Pi use openHop's Python:  /opt/openhop_repeater/venv/bin/python /opt/openhop_spamguard/replay.py ...

Your "This is spam" / "Not spam" answers in the log are treated as the truth. Messages you never
labelled are reported separately so you can check them by eye.
"""
from __future__ import annotations

import argparse
import logging
import math
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


def load_marks(path) -> list:
    """Your "spam" / "fine" answers with the moment you gave them, oldest first."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("type") == "label" and r.get("label") in ("spam", "not_spam", "none") and r.get("ts"):
                out.append(r)
    out.sort(key=lambda r: r["ts"])
    return out


def run(msgs, overrides: dict, channels: dict, quiet_step: float = 0, known_at_start: bool = False, marks=None):
    """quiet_step: when no message arrives, step the clock this far at a time instead of one poll (quicker).
    known_at_start: begin knowing the people the Pi already knew when the log starts, as it did."""
    sg.time = Clock()  # SpamGuard now runs on log time
    recorded = {m["sender"]: m.get("name_score", 0) for m in msgs}
    real_score = sg.name_score
    scrambled = all(m["sender"].startswith("N-") for m in msgs[:50]) if msgs else False
    if scrambled:
        # Names were scrambled: use the scores worked out on the Pi from the real names.
        sg.name_score = lambda name, pats: recorded.get(name, 0)
    state = os.path.join(tempfile.mkdtemp(prefix="sg-replay-"), "state.json")  # a private folder, not a guessable name
    # never the real state file or evidence log, whatever the settings say
    cfg = {"mode": "protect", "vary_limits": False, **overrides, "state_file": state, "evidence_log": False}
    g = sg.SpamGuard(cfg)
    g._save_state = lambda *a, **k: None  # a replay keeps nothing, and saving was half its running time
    if known_at_start and msgs:
        first: dict = {}
        for m in msgs:
            first.setdefault(m["sender"], m)
        for name, m in first.items():
            if m.get("known_then"):
                g.known[name] = [m["ts"] - 30 * 86400, m["ts"], 1000]
    g.cfg["channels"].update(channels)
    keys = {name: key for name, key in g.cfg["channels"].items()}
    step = g.cfg["poll_seconds"]
    out = []
    i = 0
    Clock.now = msgs[0]["ts"] if msgs else 0
    end = (msgs[-1]["ts"] + 300) if msgs else 0
    marks = list(marks or []) if overrides.get("text_sense") else []   # marks only matter to what learns from them
    mi = 0
    while Clock.now <= end:
        while mi < len(marks) and marks[mi]["ts"] <= Clock.now:
            r = marks[mi]
            mi += 1
            key = str(r.get("packet") or "") or f"{r.get('sender')}|{r.get('text')}"
            for kk in {key, f"{r.get('sender')}|{r.get('text')}"}:
                g.labels.pop(kk, None)
                if r["label"] != "none":
                    g.labels[kk] = r["label"]
            g._sense_label(key, str(r.get("text") or ""), r["label"])
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
        if quiet_step and not batch and i < len(msgs):
            # stay on the same poll ticks as a normal run, so messages are seen at the same moments
            ticks = max(1, min(int(quiet_step // step), math.ceil((msgs[i]["ts"] - Clock.now) / step)))
            Clock.now += step * ticks
        else:
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
           "by_source": {}, "missed": [], "wrong": [], "unlabelled_caught": [], "repeats": 0, "check": []}
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
            # One name sending the same thing again and again is spam behaviour whatever it says;
            # anything else held without a label is worth a look.
            if src in REPEAT_SOURCES:
                res["repeats"] += 1
            else:
                res["check"].append(m)
    return res


REPEAT_SOURCES = {"repeat", "slowrepeat", "replay"}


def level_report(msgs, overrides, channels, levels) -> dict:
    """What each protection level would have held, for SpamGuard's own page."""
    out = []
    for lv in levels:
        caught, _ = run(msgs, dict(overrides, level=lv), channels, quiet_step=60, known_at_start=True)
        r = summarise(msgs, caught)
        out.append({"level": lv, "held": r["caught"], "spam": r["spam_caught"], "repeats": r["repeats"],
                    "wrong": r["genuine_caught"], "check": len(r["check"]),
                    "check_items": [{"ts": m["ts"], "sender": m["sender"], "text": m["text"][:200],
                                     "packet": m.get("packet"), "channel": m.get("channel")} for m in r["check"][:8]],
                    "by": r["by_source"]})
    return {"from": msgs[0]["ts"] if msgs else None, "to": msgs[-1]["ts"] if msgs else None, "messages": len(msgs),
            "labelled_spam": sum(1 for m in msgs if m["_label"] == "spam"),
            "labelled_fine": sum(1 for m in msgs if m["_label"] == "not_spam"), "levels": out}


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
    ap.add_argument("--levels", help="protection levels to replay instead of the three presets, e.g. 0,50,80,100")
    ap.add_argument("--json", action="store_true", help="with --levels: print the results as JSON")
    ap.add_argument("--since", type=float, help="only messages from this Unix time on")
    ap.add_argument("--base", metavar="FILE", help="a JSON file of settings to start from")
    ap.add_argument("--only-channels", metavar="NAMES", help="only these channels, comma-separated (e.g. Public,#chat)")
    a = ap.parse_args()
    logging.disable(logging.WARNING)  # keep the report readable

    msgs, labels, marks = [], {}, []
    for p in a.log:
        m, lab, _ = load(p)
        msgs += m
        labels.update(lab)
        marks += load_marks(p)
    marks.sort(key=lambda r: r["ts"])
    msgs.sort(key=lambda r: r["ts"])
    if a.since:
        msgs = [m for m in msgs if m["ts"] >= a.since]
    skipped = 0
    if a.only_channels:
        keep = {c.strip() for c in a.only_channels.split(",") if c.strip()}
        before = len(msgs)
        msgs = [m for m in msgs if (m.get("channel") or "Public") in keep]
        skipped = before - len(msgs)
    if not msgs:
        if a.json:
            print(json.dumps({"messages": 0, "levels": []}))
            return
        sys.exit("No messages in the log. Is the evidence log switched on?")
    overrides = {}
    if a.base:
        with open(a.base, encoding="utf-8") as f:
            overrides.update(json.load(f))
    for kv in a.set:
        k, _, v = kv.partition("=")
        overrides[k] = json.loads(v) if v[:1] in "0123456789-[{tfn" else v
    channels = {t if t.startswith("#") else "#" + t: sg.hashtag_secret(t) for t in a.hashtag}
    for ch in {m.get("channel") for m in msgs}:
        if ch and ch.startswith("#"):
            channels.setdefault(ch, sg.hashtag_secret(ch))

    if a.levels:
        try:
            levels = [max(0, min(100, int(x))) for x in a.levels.split(",") if x.strip()]
        except ValueError:
            sys.exit("--levels takes numbers from 0 to 100, separated by commas")
        rep = level_report(msgs, overrides, channels, levels)
        rep["skipped"] = skipped
        if a.json:
            print(json.dumps(rep, ensure_ascii=False))
            return
        print(f"{rep['messages']} channel messages; you labelled {rep['labelled_spam']} as spam and {rep['labelled_fine']} as fine.\n")
        print(f"{'Level':<16}{'Held':>6}{'Repeats':>9}{'Your spam':>11}{'Your fine':>11}{'Worth a look':>14}")
        for r in rep["levels"]:
            print(f"{str(r['level']) + ' ' + sg.level_name(r['level']):<16}{r['held']:>6}{r['repeats']:>9}{r['spam']:>11}{r['wrong']:>11}{r['check']:>14}")
        return
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
        caught, g = run(msgs, ov, channels, marks=marks)
        r = summarise(msgs, caught)
        r["sense"] = (g.stats.get("sense_would_hold", 0), g.sense.n[1])
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
