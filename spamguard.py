#!/usr/bin/env python3
"""
openHop SpamGuard v5 - offline channel-spam protection for openHop Repeater.

Runs on the same Pi as openHop. No internet connection needed.

It reads received packets from openHop's local API, decrypts channel messages
for channels it knows, works out what is spam, and writes ordinary openHop
policy rules (named "spamguard:...") that stop your repeater forwarding it.
Rules are applied live and expire on their own when the spam stops.

The web page (default http://<pi>:8091/) has a simple view for day-to-day use
and an Advanced view with every setting explained.

Needs: Python 3.9+, pycryptodome and PyYAML (both already in openHop's venv).
"""
from __future__ import annotations

import argparse
import collections
import glob
import secrets
import shutil
import signal
import socket
import subprocess
import difflib
import hashlib
import hmac
import json
import math
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

try:
    from Crypto.Cipher import AES  # pycryptodome
except ImportError:  # pragma: no cover
    AES = None

VERSION = "5.11.4"
UPDATE_REPO = "flackrat/openhop-spamguard"  # where updates come from (owner/name on GitHub)
log = logging.getLogger("spamguard")

PAYLOAD_TYPE_GRP_TXT = 5
RULE_PREFIX = "spamguard:"
RULE_ID_BASE = 9000
PUBLIC_CHANNEL_KEY = "8b3387e9c5cdea6ac9e5edbaa115cd72"
PERMANENT_SECONDS = 10 * 365 * 86400
HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- settings
# Every tunable setting, with the wording shown on the web page.
# preset=True means the Sensitivity choice (relaxed / balanced / strict) sets it.
SETTINGS_META: list[dict] = [
    # -- Repeater (first hop) blocking
    {"key": "enable_hop_rules", "risk": "Turning this off means a spammer who keeps changing names and wording can only be caught by text rules, so more spam gets through. While on, everyone whose channel messages start at a blocked repeater is blocked too, including genuine users who rely on that repeater.", "group": "Blocking by source repeater", "type": "bool",
     "label": "Block spam at its source repeater",
     "help": "When a lot of spam enters the mesh through one repeater, block channel messages that start at that repeater."},
    {"key": "hop_match_mode", "risk": "'Anything passing through, except people it knows' still blocks a genuine person on that route until they have sent a couple of messages SpamGuard has seen, and a spammer who copies a known person's exact name gets through. 'Anything passing through' also blocks known people on any route through the spam repeater, and any other repeater sharing the same short hash. 'Routes starting there' only blocks routes it has already seen, so a spammer whose messages take a new route each time is never stopped by it.", "group": "Blocking by source repeater", "type": "choice",
     "choices": [["contains_known", "Anything passing through, except people it knows (recommended)"],
                 ["exact_paths", "Routes starting there"],
                 ["contains", "Anything passing through"]],
     "label": "How to block a repeater",
     "help": "'Except people it knows' blocks every channel message passing through the spam repeater, but lets through names SpamGuard "
             "has already seen sending genuine messages on other routes (see Known people). "
             "'Routes starting there' blocks only messages that started at the spam repeater, one learnt route at a time. "
             "'Anything passing through' blocks everything through it, including people it knows."},
    {"key": "hop_random_senders", "risk": "Lower = blocks a spam repeater sooner, but a repeater used by a couple of people with code-like names (e.g. M0ABC123) could get blocked. Higher = more spam gets out before the block starts.", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 100,
     "preset": True, "label": "Random-looking names before blocking",
     "help": "Block a repeater after this many different made-up looking names (like UD6DWREK) arrive through it in the detection window."},
    {"key": "hop_new_senders", "risk": "Lower = catches spammers using realistic names sooner, but a rally, club meet or any busy event where lots of new people talk through one repeater can trigger a block of that repeater. Higher = safer for events, slower against spam.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 200,
     "preset": True, "label": "Brand-new names before blocking",
     "help": "Block a repeater after this many names never seen before (posting once or twice) arrive through it in the detection window. "
             "Catches spammers who use realistic names. Raise this if you host busy events."},
    {"key": "hop_campaign_senders", "risk": "Lower = quicker to block a repeater carrying a spam campaign, but a few people forwarding the same news (e.g. a road closure) through one repeater could trigger it.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 100,
     "preset": True, "label": "Spam-campaign senders before blocking",
     "help": "Block a repeater after this many different names send near-identical messages through it."},
    {"key": "hop_random_senders_long", "risk": "Lower = catches slow, drip-fed spam, but over a long window a handful of genuine code-like names on a busy repeater can add up and trigger a block.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 500,
     "preset": True, "label": "Slow spam: random names over the long window",
     "help": "Catches a spammer who posts slowly to stay under the limits: block after this many random-looking names over the long window."},
    {"key": "enable_rotation_guard", "group": "Blocking by source repeater", "type": "bool",
     "risk": "While a rotation block is active, a genuine repeater that has never been heard before, sitting in the same place in the network as the spammer, is blocked until it builds up history or you allow it. Turning this off lets a spammer who keeps changing his repeater's identity get one message through per change.",
     "label": "Catch a spam repeater that keeps changing its identity",
     "help": "Some firmware lets a repeater change its ID (and so its hash) at will. The spam then arrives from a new first repeater each time, but always through the same next repeaters. SpamGuard learns which repeaters normally appear in front of each route and, when many unknown ones start sending spam the same way, blocks unknown ones there while still letting the known ones through."},
    {"key": "rotate_first_hops", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 50,
     "preset": True, "risk": "Lower = reacts to an identity-changing spammer sooner, but a couple of new genuine repeaters appearing behind the same route at the same time as some odd-looking names could trigger it. Higher = more spam gets through first.",
     "label": "Unknown repeaters before a rotation block",
     "help": "How many different never-seen-before first repeaters must deliver spam through the same route before SpamGuard treats it as one spammer changing identity. Only counts messages with strong spam signs (made-up names, disguised text or campaign copies)."},
    {"key": "route_memory_days", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 60, "unit": "days",
     "risk": "Shorter = repeaters that only talk occasionally are forgotten and may be treated as unknown during a rotation block. Longer = slightly more memory and disk use.",
     "label": "Remember normal routes for",
     "help": "How long SpamGuard remembers which repeaters normally send traffic, used to tell genuine repeaters from a spammer's changing identities."},
    {"key": "evidence_log", "group": "Evidence log", "type": "bool",
     "risk": "Stores channel messages (names and text) on the Pi for the days below. Public channel messages can be heard by anyone with a radio, but think before sharing the file: use 'names scrambled' when sending it to anyone.",
     "label": "Keep an evidence log",
     "help": "Records every channel message SpamGuard reads, with all its spam signals, whether it was caught, and your 'This is spam' / 'Not spam' answers. Download it to review what SpamGuard did, or to have the detection tuned against real traffic."},
    {"key": "evidence_days", "group": "Evidence log", "type": "int", "min": 1, "max": 30, "unit": "days",
     "risk": "Longer = more history for tuning, but more of people's messages kept on the Pi (about 1-3 MB per busy day).",
     "label": "Keep the evidence log for",
     "help": "Older days are deleted automatically."},
    {"key": "max_paths_per_hop", "risk": "Higher = more routes blocked for a stubborn spammer, but more rules for openHop to check on every message. Lower = once the limit is hit, new routes from that repeater are not blocked.", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 500,
     "label": "Most routes to learn per repeater",
     "help": "Upper limit on exact routes remembered for one blocked repeater."},
    # -- Text blocking
    {"key": "enable_text_rules", "risk": "Turning this off leaves only repeater blocks and duplicate suppression, so spam from a new location gets through until its repeater is detected. While on, a genuine message that several people repeat can be blocked.", "group": "Blocking by message text", "type": "bool",
     "label": "Block spam campaigns by their text",
     "help": "When several different names send the same or very similar message, block that text from everyone."},
    {"key": "text_distinct_senders", "risk": "Lower (2) = blocks a campaign after just two names, but two people sending the same genuine message (a net check-in, a forwarded alert) will get it blocked. Higher = more spam copies get through first.", "group": "Blocking by message text", "type": "int", "min": 2, "max": 50,
     "preset": True, "label": "Senders before a text is blocked",
     "help": "How many different names must send the same or similar message before it is treated as a spam campaign."},
    {"key": "similarity", "risk": "Lower = catches spam that has been reworded or padded with random words, but unrelated genuine messages with a lot of shared wording (templated bot replies, weather reports) may be grouped with spam. Higher = easier for the spammer to dodge by changing a few words.", "group": "Blocking by message text", "type": "int", "min": 30, "max": 100, "unit": "%",
     "preset": True, "label": "How similar counts as 'the same'",
     "help": "Messages this similar are grouped together, so adding a random word, changing case or swapping "
             "look-alike letters does not dodge the filter. 100% means identical only."},
    {"key": "min_rule_chars", "risk": "Lower = rules can be built from shorter shared text (helps with heavily varied spam), but a short rule such as 'the meeting' could block genuine messages containing it. Higher = safer, but heavily varied spam may not produce a rule at all.", "group": "Blocking by message text", "type": "int", "min": 8, "max": 80,
     "label": "Shortest text a rule may match",
     "help": "A text rule must match at least this many characters, so it never blocks something short and common."},
    # -- Duplicate suppression
    {"key": "dedupe_enabled", "risk": "While on, anyone who sends the same long message twice (resending because nobody answered, a repeated net call, several people forwarding an alert) only has the first copy forwarded. Turning it off lets a spammer repeat himself freely under new names until other rules catch up.", "group": "Duplicate suppression", "type": "bool",
     "label": "Only let the first copy of a message through",
     "help": "After any channel message is seen, the same text from anyone else is blocked for a while. "
             "Stops a spammer repeating himself under new names. Short messages are never affected."},
    {"key": "dedupe_seconds", "risk": "Longer = repeats are blocked for longer, but genuine people re-asking the same question later are blocked for longer too. Shorter = a spammer can wait it out and repeat the message.", "group": "Duplicate suppression", "type": "int", "min": 30, "max": 86400, "unit": "s",
     "preset": True, "label": "Block repeats for",
     "help": "How long the same text stays blocked after it is first seen."},
    {"key": "dedupe_min_chars", "risk": "Lower = more messages are de-duplicated, catching shorter spam, but everyday phrases like 'Is anyone receiving me?' may only get through once per period. Higher = everyday chat is safer, short spam is not de-duplicated.", "group": "Duplicate suppression", "type": "int", "min": 10, "max": 150,
     "preset": True, "label": "Only for messages at least this long",
     "help": "Messages shorter than this are never de-duplicated, so 'Morning all' or 'Anyone about?' are safe."},
    {"key": "text_rule_chars", "risk": "Shorter = harder for the spammer to dodge by editing the message, but more chance of matching a genuine message that shares that wording. Longer = more precise, but small edits can dodge it.", "group": "Duplicate suppression", "type": "int", "min": 10, "max": 150,
     "label": "Characters matched by a duplicate rule",
     "help": "A duplicate rule matches this many characters from the middle of the message, so extra words added at the start or end do not get round it."},
    # -- Known people
    {"key": "known_min_msgs", "group": "Known people", "type": "int", "min": 1, "max": 20,
     "risk": "1 = anyone who has sent one genuine-looking message on another route counts, so a spammer could get a name known by first posting something harmless. Higher = harder to fake, but genuine newcomers wait longer before they get through repeater blocks and lockdowns.",
     "label": "Genuine messages before a name counts as known",
     "help": "A name counts as known after this many genuine messages that didn't come through a blocked repeater. Names that look made-up never count. Trusted names always count."},
    {"key": "known_days", "group": "Known people", "type": "int", "min": 1, "max": 365, "unit": "days",
     "risk": "Shorter = occasional users are forgotten and treated as unknown again. Longer = a longer list kept on the Pi and in openHop.",
     "label": "Remember known names for",
     "help": "A name is forgotten if it hasn't sent anything for this long."},
    {"key": "hold_links", "group": "Known people", "type": "choice",
     "choices": [["campaign", "While a spam campaign is under way (recommended)"], ["always", "Always"], ["off", "Never"]],
     "risk": "While on, a genuine first-time poster sharing a link is held too. 'Always' does this all the time; 'while a campaign is under way' only for an hour after spam campaign activity.",
     "label": "Hold links from names it doesn't know",
     "help": "Spammers often post links. When on, channel messages containing a link (http or www.) are blocked unless the sender is a known name."},
    # -- Names
    {"key": "name_score_threshold", "risk": "Lower (1-2) = catches more made-up names, but genuine names such as callsign-plus-numbers, 'RptHill3'-style node names or 'Dave1985' may count as random and push their repeater towards a block. Higher = fewer false alarms, more spam names missed.", "group": "Sender names", "type": "int", "min": 1, "max": 6,
     "preset": True, "label": "How random a name must look",
     "help": "Names are scored 0-6 for looking machine-generated (mixed letters and digits, no vowels, odd capitals...). "
             "Names at or above this score count as random. Lower = stricter."},
    {"key": "random_name_patterns", "risk": "A pattern that is too broad (e.g. any 8 letters) marks genuine people as random. Try new patterns in Monitor mode first.", "group": "Sender names", "type": "list",
     "label": "Extra name patterns (regular expressions)",
     "help": "Optional. One regular expression per line. Names matching any of these always count as random. Matching ignores case."},
    # -- Timing
    {"key": "window_seconds", "risk": "Longer = slow spam is easier to spot, but on a busy repeater genuine new users add up and can trip the 'brand-new names' limit. Shorter = only fast bursts are detected.", "group": "Timing", "type": "int", "min": 60, "max": 86400, "unit": "s",
     "label": "Detection window",
     "help": "How far back SpamGuard looks when counting senders through a repeater."},
    {"key": "long_window_seconds", "risk": "Longer = catches very slow spam, but random-looking genuine names accumulate over the window and can add up to a block on busy repeaters.", "group": "Timing", "type": "int", "min": 600, "max": 86400, "unit": "s",
     "label": "Long window (slow spam)",
     "help": "A longer look-back used to catch spam sent slowly."},
    {"key": "block_ttl_seconds", "risk": "Longer = a spammer who pauses and returns is still blocked, but genuine users behind a wrongly blocked repeater stay blocked longer. Shorter = mistakes clear faster, but spam may return between blocks.", "group": "Timing", "type": "int", "min": 300, "max": PERMANENT_SECONDS, "unit": "s",
     "label": "Automatic blocks last for",
     "help": "Automatic blocks are removed this long after the spam stops. They are renewed while spam keeps arriving."},
    {"key": "hop_block_ttl_seconds", "risk": "Longer = a spam repeater that goes quiet for a while is still blocked when the spammer returns, but new people whose messages pass through it stay held longer. Shorter = mistakes clear sooner; a returning spammer gets a few copies through before the block starts again.", "group": "Timing", "type": "int", "min": 600, "max": PERMANENT_SECONDS, "unit": "s",
     "label": "Repeater blocks last for",
     "help": "Automatic repeater blocks end this long after the spam through that repeater stops. They're renewed while spam keeps arriving."},
    {"key": "spam_text_days", "risk": "Longer = a spam text the spammer brings back days later is stopped from its very first copy, even when openHop is running behind. Anyone quoting that exact text is also blocked until it ends (you can remove it on the page).", "group": "Timing", "type": "int", "min": 0, "max": 60, "unit": "days",
     "label": "Remember spam texts for",
     "help": "Text blocks for campaigns sent under made-up or disguised names stay in place this many days (0 = use the normal block time)."},
    {"key": "update_check", "risk": "Checking needs the Pi to reach github.com once a day; nothing else is sent. Updates are never installed until you press Update.", "group": "Updates", "type": "choice",
     "choices": [["daily", "Once a day"], ["off", "Only when I press Check"]],
     "label": "Look for new versions",
     "help": "SpamGuard can tell you when a new version is out. It only installs one when you press Update."},
    {"key": "poll_seconds", "risk": "Lower = blocks land faster, but the Pi does a little more work. Higher = more spam copies slip through before a rule exists.", "group": "Timing", "type": "int", "min": 1, "max": 300, "unit": "s",
     "label": "Check for new packets every",
     "help": "Lower is faster to react. 3 seconds is a good balance."},
    {"key": "max_total_rules", "risk": "Higher = nothing is dropped during a very heavy attack, but every rule is checked against every channel message, which costs CPU on small Pis. Lower = the oldest duplicate rules are dropped first.", "group": "Timing", "type": "int", "min": 20, "max": 2000,
     "label": "Most rules at once",
     "help": "Safety limit on rules written to openHop. The oldest duplicate rules are dropped first."},
]
META_BY_KEY = {m["key"]: m for m in SETTINGS_META}

PRESETS: dict[str, dict] = {
    "relaxed": {"rotate_first_hops": 4, "hop_random_senders": 5, "hop_new_senders": 10, "hop_campaign_senders": 5,
                "hop_random_senders_long": 8, "text_distinct_senders": 4, "similarity": 80,
                "dedupe_seconds": 600, "dedupe_min_chars": 40, "name_score_threshold": 4},
    "balanced": {"rotate_first_hops": 3, "hop_random_senders": 3, "hop_new_senders": 6, "hop_campaign_senders": 3,
                 "hop_random_senders_long": 5, "text_distinct_senders": 3, "similarity": 65,
                 "dedupe_seconds": 900, "dedupe_min_chars": 30, "name_score_threshold": 3},
    "strict": {"rotate_first_hops": 2, "hop_random_senders": 2, "hop_new_senders": 4, "hop_campaign_senders": 2,
               "hop_random_senders_long": 3, "text_distinct_senders": 2, "similarity": 55,
               "dedupe_seconds": 1800, "dedupe_min_chars": 24, "name_score_threshold": 2},
}

DEFAULT_CONFIG: dict[str, Any] = {
    "openhop_url": "http://127.0.0.1:8000",
    "api_key": "",
    "mode": "monitor",                    # monitor | protect
    "paused": False,
    "sensitivity": "balanced",            # relaxed | balanced | strict
    "channels": {"Public": PUBLIC_CHANNEL_KEY},
    "hashtag_channels": [],               # e.g. ["#test", "#chat"] - keys are worked out from the name
    "enable_hop_rules": True,
    "hop_match_mode": "contains_known",
    "known_min_msgs": 1,
    "known_days": 30,
    "hold_links": "campaign",
    "max_paths_per_hop": 50,
    "enable_rotation_guard": True,
    "route_memory_days": 7,
    "evidence_log": False,
    "evidence_days": 7,
    "evidence_dir": "/var/lib/openhop_spamguard/evidence",
    "max_origins_per_route": 60,
    "enable_text_rules": True,
    "min_rule_chars": 14,
    "dedupe_enabled": True,
    "text_rule_chars": 40,
    "random_name_patterns": [r"(?=.*\d)(?=.*[a-z])[a-z0-9]{8}"],
    "window_seconds": 600,
    "long_window_seconds": 7200,
    "block_ttl_seconds": 6 * 3600,
    "spam_text_days": 7,
    "hop_block_ttl_seconds": 2 * 3600,
    "update_check": "daily",
    "update_repo": UPDATE_REPO,
    "poll_seconds": 3,
    "fetch_limit": 500,
    "max_total_rules": 300,
    "min_sync_seconds": 2,
    "allow_hops": [],
    "allow_senders": [],
    "allow_texts": [],
    "listen_host": "0.0.0.0",
    "listen_port": 8091,
    "listen_api_key": "",
    "state_file": "/var/lib/openhop_spamguard/state.json",
    **PRESETS["balanced"],
}
# Settings the page may change, besides those in SETTINGS_META.
EXTRA_TUNABLES = {"mode", "paused", "sensitivity"}
LEGACY_KEYS = {"hop_one_shot_senders": "hop_new_senders"}


# --------------------------------------------------------------------------- crypto
def _secret32(secret_hex: str) -> bytes:
    b = bytes.fromhex(secret_hex)
    return (b + b"\x00" * 32)[:32]


def channel_hash_byte(secret_hex: str) -> int:
    b = bytes.fromhex(secret_hex)
    if len(b) >= 32 and b[16:32] == b"\x00" * 16:
        b = b[:16]
    return hashlib.sha256(b[:32]).digest()[0]


def hashtag_secret(name: str) -> str:
    """MeshCore hashtag channels: secret = SHA-256('#name')[:16]."""
    name = name.strip()
    if not name.startswith("#"):
        name = "#" + name
    return hashlib.sha256(name.encode("utf-8")).digest()[:16].hex()


def decrypt_group_text(payload: bytes, channels: dict[str, str]) -> Optional[dict]:
    """Return {'channel','sender','text'} for a GroupText payload, or None."""
    if AES is None or len(payload) < 4:
        return None
    ch_hash, mac, ct = payload[0], payload[1:3], payload[3:]
    for name, secret in channels.items():
        try:
            if channel_hash_byte(secret) != ch_hash:
                continue
            key = _secret32(secret)
            if hmac.new(key, ct, hashlib.sha256).digest()[:2] != mac:
                continue
            padded = ct + b"\x00" * ((-len(ct)) % 16)
            pt = AES.new(key[:16], AES.MODE_ECB).decrypt(padded)[: len(ct)]
            # [timestamp 4][flags 1]["sender: text"][zero padding]
            msg = pt[5:].split(b"\x00", 1)[0].decode("utf-8", "replace")
            sender, text = (msg.split(": ", 1) if ": " in msg else ("", msg))
            return {"channel": name, "sender": sender.strip(), "text": text}
        except Exception:
            continue
    return None


# --------------------------------------------------------------------------- text analysis
ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­᠎"), None)
# Look-alike letters (Cyrillic/Greek) and leetspeak -> Latin
CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "һ": "h", "ӏ": "l", "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
    "α": "a", "ο": "o", "ρ": "p", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "τ": "t", "υ": "u", "χ": "x",
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "l",
})
# Emoji and the invisible pieces used to build them.
EMOJI_BASE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\u3030\u303D\u3297\u3299]")
EMOJI_PARTS = re.compile("[\U0001F3FB-\U0001F3FF\uFE0E\uFE0F\u200D\u20E3\U000E0020-\U000E007F]")
TAG_CHARS = re.compile("[\U000E0000-\U000E007F]")  # invisible "tag" letters, abused to hide text
EMOJI_ANY = re.compile(EMOJI_BASE.pattern[:-1] + EMOJI_PARTS.pattern[1:-1] + "]")


def strip_emoji(text: str) -> str:
    return EMOJI_ANY.sub("", text)


def emoji_tokens(text: str) -> list[str]:
    """Base emoji only: skin tones, colour variants and joiners don't make a message different."""
    return [f"{ord(c):x}" for c in text if EMOJI_BASE.match(c) and not EMOJI_PARTS.match(c)]


LATIN = re.compile(r"[A-Za-z]")
NON_LATIN_LETTER = re.compile(r"[Ͱ-ϿЀ-ӿ]")


MENTION = re.compile(r"@\[[^\]\n]{1,48}\]")  # "@[Rob-M0YNW]": who a reply is to, not what it says


def strip_mentions(text: str) -> str:
    """Replace @[name] mentions with a line break, so shared text is never just someone's name
    and rule text never spans a mention (each piece stays a real part of the message)."""
    return MENTION.sub("\n", text)


def longest_piece(text: str) -> str:
    return max((p.strip() for p in text.split("\n")), key=len, default="")


def normalise(text: str) -> str:
    """Fold case, strip invisible characters and emoji, map look-alikes, collapse punctuation.
    @[name] mentions are left out. Messages that are (nearly) all emoji are described by their emoji instead."""
    text = MENTION.sub(" ", text)
    t = unicodedata.normalize("NFKC", TAG_CHARS.sub("", text)).translate(ZERO_WIDTH).casefold()
    t = "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch))
    t = t.translate(CONFUSABLES)
    words = re.sub(r"[^a-z0-9]+", " ", t).strip()
    if len(words.replace(" ", "")) < 8:
        emo = emoji_tokens(text)
        if len(emo) >= 3:
            return ("emoji " + " ".join(emo) + " " + words).strip()
    return words


def shingles(norm: str, n: int = 4) -> frozenset:
    s = norm.replace(" ", "")
    if len(s) <= n:
        return frozenset([s]) if s else frozenset()
    return frozenset(s[i:i + n] for i in range(len(s) - n + 1))


def is_obfuscated(text: str, name: bool = False) -> bool:
    """Tricks used to make copies of a message look different:
    hidden characters or emoji placed inside words, invisible tag letters,
    or Latin words mixed with look-alike Cyrillic/Greek letters.
    Ordinary emoji between words, and joiners inside emoji (e.g. family emoji) are fine."""
    if TAG_CHARS.search(text) and not re.search("\U0001F3F4[\U000E0020-\U000E007F]+\U000E007F", text):
        return True  # tag letters, other than in subdivision flags such as England's
    hidden = "\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e"
    if re.search(f"[A-Za-z0-9][{hidden}]+[A-Za-z0-9]", text) or re.search(f"[\u200b\u2060\ufeff\u00ad\u180e]", text):
        return True
    # An emoji wedged between letters of one word: "Bu🔥ilt". Not for display names, where a
    # symbol inside the name is just styling ("HDZ✝rt").
    if not name and re.search("[A-Za-z]" + EMOJI_ANY.pattern + "+[A-Za-z]", text):
        return True
    for word in re.findall(r"\w+", text):
        if LATIN.search(word) and NON_LATIN_LETTER.search(word):
            return True
    return False


def name_score(name: str, patterns: list) -> int:
    """0-6: how machine-generated a sender name looks. Emoji are ignored, so adding one
    ("UD6DWREK🔥") doesn't hide a random name, and emoji in a genuine name don't count against it."""
    score = 0
    raw = name.strip()
    plain = strip_emoji(raw).strip()
    if raw and not plain:
        # Emoji-only names: unusual, and a mix of 3+ different emoji looks generated.
        return 3 if len(set(emoji_tokens(raw))) >= 3 else 1
    if any(p.fullmatch(plain) for p in patterns):
        score += 2
    # Only judge single-word, letters-and-digits names; "Dave M", "BOT-01-X", "Ohm🔌" are left alone.
    if not re.fullmatch(r"[A-Za-z0-9]{6,16}", plain):
        return min(score, 6)
    # "Dave1985", "Bob42", "Sarah2": a word followed by a number reads as a person.
    if re.fullmatch(r"[A-Z]?[a-z]{2,}\d{1,4}", plain):
        return 1
    # Lower-case "l33t" names ("r3dm0zzy" = redmozzy) read as a word once the digits are turned back.
    if plain[1:] == plain[1:].lower() and re.search(r"\d", plain):
        word = plain.lower().translate(str.maketrans("013457", "oieast"))
        if word.isalpha() and len(re.findall(r"[aeiouy]", word)) / len(word) >= 0.25 \
                and max((len(r) for r in re.findall(r"[^aeiouy]+", word)), default=0) <= 3:
            return 1
    letters = re.sub(r"[^A-Za-z]", "", plain)
    if letters and re.search(r"\d", plain):
        score += 1
    classes = ["d" if c.isdigit() else "l" for c in plain]
    if sum(1 for a, b in zip(classes, classes[1:]) if a != b) >= 3:
        score += 1
    low = letters.lower()
    if len(re.findall(r"[aeiouy]", low)) / max(len(low), 1) < 0.15 and len(low) >= 4:
        score += 1
    if max((len(r) for r in re.findall(r"[^aeiouy\d]+", low)), default=0) >= 4:
        score += 1
    if letters.isupper() and len(letters) >= 5:
        score += 1
    else:
        cases = ["u" if c.isupper() else "l" for c in letters]
        if sum(1 for a, b in zip(cases, cases[1:]) if a != b) >= 4:
            score += 1
    return min(score, 6)


def middle_chunk(text: str, length: int) -> str:
    """A whole-word piece from the middle of the text (robust to words added at either end)."""
    t = text.strip()
    if len(t) <= length:
        return t
    start = (len(t) - length) // 2
    if start > 0 and not t[start - 1].isspace():
        sp = t.find(" ", start, start + 12)
        if sp != -1:
            start = sp + 1
    end = min(len(t), start + length)
    if end < len(t) and not t[end].isspace():
        sp = t.rfind(" ", start + length // 2, end)
        if sp != -1:
            end = sp
    return t[start:end].strip()


def weighted_len(t: str) -> int:
    """Length for rule-safety purposes: each emoji counts as 3 characters, so a run of emoji
    can form a rule, while a single 👍 never does."""
    return len(strip_emoji(t)) + 3 * len(emoji_tokens(t))


def common_words(texts: list[str], minimum: int, most: int = 4) -> Optional[list[str]]:
    """Longest words found in every copy, exactly as written. An openHop rule requiring all of them
    catches copies with emoji or symbols sprinkled between the words."""
    def words(t):
        out = []
        for w in re.split(r"\s+", strip_emoji(t)):
            w = w.strip(".,!?;:'\"()[]{}-_*~")
            if len(w) >= 4 and re.fullmatch(r"[\w'&+/.-]+", w):
                out.append(w)
        return out
    if len(texts) < 2:
        return None
    first = words(texts[0])
    shared = [w for w in dict.fromkeys(first) if all(w in t for t in texts[1:])]
    shared.sort(key=len, reverse=True)
    pick = shared[:most]
    if len(pick) < 3 or sum(map(len, pick)) < minimum:
        return None
    return sorted(pick, key=lambda w: texts[0].find(w))


def common_substring(texts: list[str], minimum: int) -> Optional[str]:
    """Longest piece of text shared by every variant (what an openHop 'contains' rule can match)."""
    if not texts:
        return None
    common = texts[0]
    for t in texts[1:]:
        m = difflib.SequenceMatcher(None, common, t, autojunk=False).find_longest_match(0, len(common), 0, len(t))
        common = common[m.a:m.a + m.size]
        if weighted_len(common) < minimum:
            return None
    # Drop a word cut in half at either end in any of the messages (rules read better and
    # match whole words only).
    for t in texts:
        i = t.find(common)
        if i == -1:
            continue
        if i > 0 and t[i - 1].isalnum() and common[:1].isalnum():
            common = common.split(" ", 1)[1] if " " in common else ""
            i = t.find(common)
        j = i + len(common)
        if 0 <= i and j < len(t) and t[j].isalnum() and common[-1:].isalnum():
            common = common.rsplit(" ", 1)[0] if " " in common else ""
    common = common.strip()
    if len(common) > 100:
        common = middle_chunk(common, 100)
    return common if weighted_len(common) >= minimum else None


# --------------------------------------------------------------------------- helpers
def parse_path(value: Any) -> list[str]:
    if value in (None, "", "null"):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            value = [p for p in re.split(r"[,>\s]+", value) if p]
    if not isinstance(value, list):
        return []
    out = []
    for h in value:
        s = str(h).strip()
        if s.lower().startswith("0x"):
            s = s[2:]
        if s:
            out.append(s.upper())
    return out


def text_key(snippet: str) -> str:
    return "text:" + hashlib.sha1(snippet.encode()).hexdigest()[:10]


def hops_related(a: str, b: str) -> bool:
    """Same repeater at different hash widths: '27' relates to '27AB' and '27AB01'."""
    return a.startswith(b) or b.startswith(a)


HEX_HOP = re.compile(r"[0-9A-F]{2}|[0-9A-F]{4}|[0-9A-F]{6}")


# --------------------------------------------------------------------------- service health
def sd_notify(message: str) -> bool:
    """Tell systemd we're alive (READY=1 / WATCHDOG=1). Does nothing when not run by systemd."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr[0] == "@":
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(message.encode())
        return True
    except OSError:
        return False


def _read(path: str) -> Optional[str]:
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return None


_svc_cache: dict[str, tuple] = {}


def systemd_value(unit: str, prop: str) -> Optional[str]:
    """Ask systemd about a service (cached for a minute). None if systemd isn't available."""
    key = unit + prop
    hit = _svc_cache.get(key)
    if hit and time.time() - hit[0] < 60:
        return hit[1]
    val = None
    try:
        env = {k: v for k, v in os.environ.items() if k not in ("NOTIFY_SOCKET", "WATCHDOG_USEC", "WATCHDOG_PID")}
        out = subprocess.run(["systemctl", "show", unit, "-p", prop, "--value"],
                             capture_output=True, text=True, timeout=3, env=env)
        if out.returncode == 0:
            val = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    _svc_cache[key] = (time.time(), val)
    return val


def system_readings(folder: str) -> dict:
    out: dict[str, Any] = {}
    up = _read("/proc/uptime")
    if up:
        out["pi_uptime"] = float(up.split()[0])
    try:
        out["load"] = round(os.getloadavg()[0], 2)
        out["cpus"] = os.cpu_count() or 1
    except OSError:
        pass
    t = _read("/sys/class/thermal/thermal_zone0/temp")
    if t and t.strip().lstrip("-").isdigit():
        out["temp_c"] = round(int(t) / 1000, 1)
    mem = _read("/proc/meminfo")
    if mem:
        m = {l.split(":")[0]: int(l.split()[1]) for l in mem.splitlines() if l.split()[1:2] and l.split()[1].isdigit()}
        if "MemTotal" in m and "MemAvailable" in m:
            out["mem_avail_pct"] = round(100 * m["MemAvailable"] / m["MemTotal"])
    st = _read("/proc/self/status")
    if st:
        for l in st.splitlines():
            if l.startswith("VmRSS:"):
                out["rss_mb"] = round(int(l.split()[1]) / 1024)
    try:
        d = shutil.disk_usage(folder if os.path.isdir(folder) else "/")
        out["disk_free_mb"] = round(d.free / 1048576)
    except OSError:
        pass
    return out


def name_shape(name: str) -> str:
    """The look of a name without the name: A=capital, a=small letter, 9=digit, E=emoji."""
    out = []
    for c in name:
        if EMOJI_BASE.match(c):
            out.append("E")
        elif EMOJI_PARTS.match(c):
            continue
        elif c.isdigit():
            out.append("9")
        elif c.isalpha():
            out.append("A" if c.isupper() else "a")
        else:
            out.append(c if c in " -_.'" else "?")
    return "".join(out)


class EvidenceLog:
    """One JSON line per channel message (plus your labels, block changes and settings), written to a
    file per day. Writes are batched to spare the SD card; old days are deleted automatically."""

    def __init__(self, folder: str):
        self.folder = folder
        self.buf: list[str] = []
        self.last_flush = time.time()
        self.lock = threading.Lock()

    def add(self, record: dict):
        record.setdefault("ts", round(time.time(), 2))
        with self.lock:
            self.buf.append(json.dumps(record, ensure_ascii=False, default=str))

    def flush(self, force=False, keep_days=7):
        with self.lock:
            if not self.buf or (not force and len(self.buf) < 200 and time.time() - self.last_flush < 60):
                return
            lines, self.buf = self.buf, []
            self.last_flush = time.time()
        try:
            os.makedirs(self.folder, exist_ok=True)
            by_day: dict[str, list[str]] = {}
            for ln in lines:
                day = time.strftime("%Y-%m-%d", time.localtime(json.loads(ln)["ts"]))
                by_day.setdefault(day, []).append(ln)
            for day, ls in by_day.items():
                with open(os.path.join(self.folder, f"{day}.jsonl"), "a", encoding="utf-8") as f:
                    f.write("\n".join(ls) + "\n")
            cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - keep_days * 86400))
            for fpath in self.files():
                if os.path.basename(fpath)[:10] < cutoff:
                    os.remove(fpath)
        except Exception as e:
            log.warning("Could not write evidence log: %s", e)

    def files(self) -> list[str]:
        # Only SpamGuard's own day files (YYYY-MM-DD.jsonl), never anything else in the folder.
        return sorted(glob.glob(os.path.join(self.folder, "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].jsonl")))

    def summary(self) -> dict:
        fs = self.files()
        return {"days": len(fs), "bytes": sum(os.path.getsize(f) for f in fs),
                "first": os.path.basename(fs[0])[:10] if fs else None, "pending": len(self.buf)}

    def export(self, days: int, scramble: bool) -> str:
        self.flush(force=True)
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - (days - 1) * 86400))
        lines = []
        for fpath in self.files():
            if os.path.basename(fpath)[:10] >= cutoff:
                with open(fpath, encoding="utf-8") as f:
                    lines.extend(l for l in f.read().splitlines() if l.strip())
        if not scramble:
            return "\n".join(lines) + ("\n" if lines else "")
        salt = secrets.token_hex(8)
        names: dict[str, str] = {}

        def code(n):
            if n not in names:
                names[n] = "N-" + hashlib.sha256((salt + n).encode()).hexdigest()[:6]
            return names[n]

        recs = []
        for ln in lines:
            try:
                recs.append(json.loads(ln))
            except ValueError:
                continue
        for r in recs:  # learn every name first so mentions of people can be replaced too
            for k in ("sender", "exempt_sender"):
                if r.get(k):
                    code(r[k])
        known = sorted(names, key=len, reverse=True)
        out = []
        for r in recs:
            for k in ("sender", "exempt_sender"):
                if r.get(k):
                    r[k] = code(r[k])
            for k in ("text", "msg", "value"):
                if isinstance(r.get(k), str):
                    t = re.sub(r"@\[([^\]]+)\]", lambda m: "@[" + code(m.group(1)) + "]", r[k])
                    for n in known:
                        if len(n) >= 3:
                            t = t.replace(n, names[n])
                    r[k] = t
            out.append(json.dumps(r, ensure_ascii=False))
        return "\n".join(out) + ("\n" if out else "")


class Event:
    __slots__ = ("ts", "path", "first_hop", "sender", "text", "channel", "norm", "shingles",
                 "name_score", "random", "obfuscated", "matched", "campaign", "exempt", "recorded", "logged", "packet", "seen_at",
                 "length")

    def __init__(self, ts, path, sender, text, channel):
        self.ts = ts
        self.path = path
        self.first_hop = path[0] if path else "DIRECT"
        self.sender = sender
        self.text = text
        self.channel = channel
        self.norm = normalise(text)
        self.shingles = shingles(self.norm)
        self.name_score = 0
        self.random = False
        # @[name] mentions are someone else's name, not this message's text
        self.obfuscated = is_obfuscated(MENTION.sub(" ", text)) or is_obfuscated(sender, name=True)
        self.matched: Optional[str] = None
        self.campaign: Optional[int] = None
        self.exempt = False
        self.recorded = False
        self.logged = False
        self.packet = ""
        self.seen_at = ts
        self.length = 0


# --------------------------------------------------------------------------- core
class SpamGuard:
    def __init__(self, cfg_file: dict):
        self.file_cfg = cfg_file
        self.lock = threading.RLock()
        self.events: collections.deque[Event] = collections.deque()
        self.seen_packets: collections.OrderedDict[str, float] = collections.OrderedDict()
        # Packets already written to the evidence log. Kept across restarts, because on start-up
        # openHop's recent packets are read again to rebuild the picture.
        self.logged_packets: collections.OrderedDict[str, None] = collections.OrderedDict()
        self.counted_packets: collections.OrderedDict[str, None] = collections.OrderedDict()  # already counted
        self.last_packet_ts: Optional[float] = None    # newest packet of any kind openHop reported
        self.heard_at: Optional[float] = None          # when that last moved forward
        # How far behind real time openHop's packet list is: (when measured, seconds behind)
        self.lag_samples: collections.deque[tuple] = collections.deque(maxlen=200)
        self.use_filtered: Optional[bool] = None   # openHop's /api/filtered_packets available?
        self.update_info: dict = {"latest": None, "notes": "", "url": "", "checked": None, "error": None}
        self._update_checking = False
        self.sender_history: dict[str, dict] = {}  # name -> {first, count, hops:set}
        self.blocks: dict[str, dict] = {}
        self.suppressed: dict[str, float] = {}
        self.allow_hops: set[str] = set()
        self.allow_senders: set[str] = set()
        self.allow_texts: set[str] = set()
        self.extra_channels: dict[str, str] = {}
        self.settings: dict[str, Any] = {}  # changes made on the web page
        self.next_rule_id = RULE_ID_BASE
        self.activity: collections.deque[dict] = collections.deque(maxlen=300)
        self.catches: collections.deque[float] = collections.deque(maxlen=50000)
        self.stats = collections.Counter()
        self.last_poll_ok: Optional[float] = None
        self.last_error: Optional[str] = None
        self.last_sync: Optional[float] = None
        self.sync_pending = False
        self.evidence: Optional[EvidenceLog] = None
        self.started = time.time()
        self.loop_beat: Optional[float] = None    # end of the last check loop, success or not
        self.loop_count = 0
        self.poll_ms: Optional[int] = None
        self.openhop_ms: Optional[int] = None
        self.errors: collections.deque[float] = collections.deque(maxlen=500)
        self.openhop_down_since: Optional[float] = None
        self.rules_seen: Optional[int] = None     # SpamGuard rules found in openHop at the last check
        self.rules_expected: Optional[int] = None
        self.last_verify = 0.0
        self.self_heals = 0
        self._last_save = 0.0
        self.clusters: dict[int, dict] = {}
        # Learnt network shape: route -> [first_seen, last_seen, good, bad]; hash -> last time it relayed
        self.routes: dict[str, list] = {}
        self.relays: dict[str, float] = {}
        # Names seen sending genuine messages: name -> [first_seen, last_seen, genuine messages]
        self.known: dict[str, list] = {}
        self._important = False  # something worth saving to the SD card straight away
        self.removed_sender_blocks: list = []
        # Messages held from normal-looking names: the likely mistakes, shown on the page
        self.held: collections.deque[dict] = collections.deque(maxlen=60)
        # Hourly history for the overview: hour -> {m: messages, c: spam stopped, x: spam let through,
        # g: genuine-looking held, a: airtime saved (ms), h: {first repeater: spam}}
        self.hist: dict[str, dict] = {}
        self.hist_mark = 0.0          # newest message already counted (so restarts don't count twice)
        self.radio: dict = {}         # openHop's radio settings, for airtime
        self.me: dict = {}            # this repeater: name, hash, location
        self.repeaters: dict = {"ts": 0, "list": []}   # repeaters openHop has heard adverts from
        self.rule_ids: dict[str, int] = {}   # ids of shared rules (e.g. "let known people through")
        self.cfg: dict[str, Any] = {}
        self._load_state()
        self.rebuild_cfg()
        for name in self.removed_sender_blocks:
            self.note(f"Removed the block on the name \"{name}\": SpamGuard now only blocks spam behaviour, "
                      "not named people. Muting someone is best done in your own MeshCore app.")
            self._important = True
        if not self.known and self.sender_history:
            # First start of a version with known people: begin with the names heard in the
            # last day that don't look made-up, so people aren't all strangers after an update.
            for name, h in self.sender_history.items():
                if name and name != "?" and not is_obfuscated(name, name=True) \
                        and name_score(name, self.name_res) < self.cfg["name_score_threshold"]:
                    self.known[name] = [h["first"], h["first"], h["count"]]

    # ---- configuration layering: defaults < sensitivity preset < config file < web page
    def rebuild_cfg(self):
        sens = self.settings.get("sensitivity") or self.file_cfg.get("sensitivity") or "balanced"
        if sens not in PRESETS:
            sens = "balanced"
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        cfg.update(PRESETS[sens])
        cfg.update(self.file_cfg)
        cfg.update(self.settings)
        cfg["sensitivity"] = sens
        if cfg.get("mode") not in ("monitor", "protect"):
            cfg["mode"] = "monitor"
        channels = dict(cfg.get("channels") or {})
        for tag in cfg.get("hashtag_channels") or []:
            channels[tag if tag.startswith("#") else "#" + tag] = hashtag_secret(tag)
        channels.update(self.extra_channels)
        cfg["channels"] = channels
        self.cfg = cfg
        self.allow_hops |= {h.upper() for h in cfg.get("allow_hops") or []}
        self.allow_senders |= set(cfg.get("allow_senders") or [])
        self.allow_texts |= set(cfg.get("allow_texts") or [])
        self.name_res = [re.compile(p, re.I) for p in cfg.get("random_name_patterns") or []]
        if cfg.get("evidence_log"):
            if self.evidence is None or self.evidence.folder != cfg["evidence_dir"]:
                self.evidence = EvidenceLog(cfg["evidence_dir"])
        elif self.evidence is not None:
            self.evidence.flush(force=True, keep_days=cfg["evidence_days"])
            self.evidence = None

    def ev(self, record: dict):
        if self.evidence is not None:
            self.evidence.add(record)

    def log_messages(self, events):
        """Write settled messages to the evidence log (after campaigns have had time to show)."""
        if self.evidence is None:
            return
        now = time.time()
        for e in events:
            if e.logged or now - e.ts < 120:
                continue
            e.logged = True
            if e.packet:
                if e.packet in self.logged_packets:
                    continue  # already logged before a restart
                self.logged_packets[e.packet] = None
                while len(self.logged_packets) > 3000:
                    self.logged_packets.popitem(last=False)
            h = self.sender_history.get(e.sender, {})
            b = self.blocks.get(e.matched) if e.matched else None
            cc = self.clusters.get(e.campaign) if e.campaign is not None else None
            self.ev({"type": "msg", "ts": round(e.ts, 2), "packet": e.packet, "channel": e.channel,
                     "sender": e.sender, "shape": name_shape(e.sender), "text": e.text,
                     "path": e.path, "hops": len(e.path), "name_score": e.name_score, "random": e.random,
                     "obfuscated": e.obfuscated, "trusted": e.sender in self.allow_senders, "known": self.is_known(e.sender), "exempt": e.exempt,
                     "sender_count_24h": h.get("count"), "sender_first_seen": round(h.get("first", e.ts), 2),
                     "campaign_senders": len(cc["senders"]) if cc else 0,
                     "origin_known": bool(e.path) and self.known_origin(e.first_hop),
                     "seen_after_s": round(e.seen_at - e.ts, 1),
                     "caught_by": e.matched, "caught_kind": b["kind"] if b else None,
                     "caught_source": b.get("source") if b else None,
                     "mode": "paused" if self.cfg.get("paused") else self.cfg["mode"]})

    def snapshot_settings(self, why: str):
        self.ev({"type": "settings", "why": why, "version": VERSION,
                 "sensitivity": self.cfg["sensitivity"], "mode": self.cfg["mode"], "paused": bool(self.cfg.get("paused")),
                 "settings": {m["key"]: self.cfg.get(m["key"]) for m in SETTINGS_META}})

    def note(self, msg: str, journal: bool = True):
        if journal:  # routine duplicate notes stay off the system log (fewer SD card writes)
            log.warning(msg)
        self.activity.appendleft({"ts": time.time(), "msg": msg})
        self.ev({"type": "note", "msg": msg})

    # ---- state ----
    def _load_state(self):
        try:
            with open(self.file_cfg.get("state_file", DEFAULT_CONFIG["state_file"])) as f:
                st = json.load(f)
        except FileNotFoundError:
            return
        except Exception as e:
            log.warning("Could not load state: %s", e)
            return
        now = time.time()
        self.blocks = {k: v for k, v in st.get("blocks", {}).items() if v.get("expires", 0) > now}
        # 5.10 briefly had blocks on a sender's name; SpamGuard judges behaviour, not people, so they go.
        self.removed_sender_blocks = [v.get("value") for k, v in self.blocks.items() if v.get("kind") == "sender"]
        self.blocks = {k: v for k, v in self.blocks.items() if v.get("kind") != "sender"}
        self.suppressed = {k: v for k, v in st.get("suppressed", {}).items() if v > now}
        self.allow_hops = set(st.get("allow_hops", []))
        self.allow_senders = set(st.get("allow_senders", []))
        self.allow_texts = set(st.get("allow_texts", []))
        self.extra_channels = dict(st.get("extra_channels", {}))
        settings = {}
        for k, v in (st.get("settings") or {}).items():
            k = LEGACY_KEYS.get(k, k)
            if k == "action":  # v4 and earlier
                settings["mode"] = "protect" if v == "drop" else "monitor"
            elif k in META_BY_KEY or k in EXTRA_TUNABLES:
                settings[k] = v
        self.settings = settings
        self.next_rule_id = int(st.get("next_rule_id", RULE_ID_BASE))
        self.activity.extend(st.get("activity", [])[:300])
        self.catches.extend(t for t in st.get("catches", []) if t > now - 86400)
        self.routes = {k: v for k, v in (st.get("routes") or {}).items() if isinstance(v, list) and len(v) == 4}
        self.relays = dict(st.get("relays") or {})
        self.logged_packets = collections.OrderedDict((p, None) for p in (st.get("logged_packets") or [])[-3000:])
        self.counted_packets = collections.OrderedDict((p, None) for p in (st.get("counted_packets") or [])[-3000:])
        self.known = {k: v for k, v in (st.get("known_senders") or {}).items() if isinstance(v, list) and len(v) == 3}
        self.rule_ids = {k: int(v) for k, v in (st.get("rule_ids") or {}).items()}
        self.hist = {k: v for k, v in (st.get("hist") or {}).items() if isinstance(v, dict) and int(k) > now - 8 * 86400}
        self.hist_mark = float(st.get("hist_mark") or 0)
        self.held.extend(h for h in (st.get("held") or []) if isinstance(h, dict) and h.get("ts", 0) > now - 86400)
        for name, v in (st.get("senders") or {}).items():
            if isinstance(v, list) and len(v) == 2 and v[0] > now - 86400:
                self.sender_history[name] = {"first": v[0], "count": int(v[1]), "hops": set()}
        for b in self.blocks.values():
            b.setdefault("hits", 0)
            b.setdefault("source", "manual" if b.get("manual") else ("hop" if b.get("kind") == "hop" else "campaign"))
            if b.get("kind") == "hop":
                b.setdefault("paths", {})
            if "id" not in b:
                b["id"] = self._new_id()

    def _save_state(self, force=False):
        """Written straight away for important changes, otherwise at most every 5 minutes, to spare
        the SD card. Short-lived duplicate rules don't count: losing them in a power cut is harmless.
        A clean stop (restart, update) always saves."""
        now = time.time()
        if not force and now - self._last_save < 300:
            return
        self._last_save = now
        self._important = False
        path = self.cfg.get("state_file") or self.file_cfg.get("state_file", DEFAULT_CONFIG["state_file"])
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({
                    "version": VERSION,
                    "blocks": self.blocks,
                    "suppressed": self.suppressed,
                    "allow_hops": sorted(self.allow_hops),
                    "allow_senders": sorted(self.allow_senders),
                    "allow_texts": sorted(self.allow_texts),
                    "extra_channels": self.extra_channels,
                    "settings": self.settings,
                    "next_rule_id": self.next_rule_id,
                    "activity": list(self.activity)[:300],
                    "catches": [t for t in self.catches if t > now - 86400],
                    "routes": self.routes,
                    "relays": self.relays,
                    "logged_packets": list(self.logged_packets),
                    "counted_packets": list(self.counted_packets),
                    "known_senders": self.known,
                    "held": list(self.held),
                    "hist": self.hist,
                    "hist_mark": self.hist_mark,
                    "rule_ids": self.rule_ids,
                    "senders": {k: [round(v["first"], 1), v["count"]]
                                for k, v in list(self.sender_history.items())[-3000:]},
                }, f)
            os.replace(tmp, path)
        except Exception as e:
            log.warning("Could not save state: %s", e)

    def reset_all(self):
        """Back to a fresh install, keeping only Monitor/Protect, channels you added, the charts and the
        evidence log. Removed blocks don't wait 24 hours: detection starts again straight away."""
        mode = self.cfg.get("mode", "monitor")
        n = len(self.blocks)
        self.blocks.clear()
        self.suppressed.clear()
        self.allow_hops.clear()
        self.allow_senders.clear()
        self.allow_texts.clear()
        self.settings = {"mode": mode} if mode != DEFAULT_CONFIG["mode"] else {}
        self.routes.clear()
        self.relays.clear()
        self.clusters.clear()
        self.held.clear()
        self.rule_ids.clear()
        for e in self.events:            # recent messages are judged again under the fresh rules
            e.matched = None
        self.rebuild_cfg()
        # Same starting point as a new install reading openHop's recent traffic: names heard in the
        # last day that don't look made-up count as known, so regulars aren't all held at first.
        self.known = {}
        for name, h in self.sender_history.items():
            if name and name != "?" and not is_obfuscated(name, name=True) \
                    and name_score(name, self.name_res) < self.cfg["name_score_threshold"]:
                self.known[name] = [h["first"], h["first"], h["count"]]
        self.note(f"Started again from scratch: {n} block{'' if n == 1 else 's'}, all settings and exceptions "
                  f"cleared ({'Protect' if mode == 'protect' else 'Monitor'} mode kept)")
        self._important = True

    def _new_id(self) -> int:
        used = set()
        for b in self.blocks.values():
            used.add(b.get("id"))
            used.update((b.get("paths") or {}).values())
            used.update((b.get("allow_ids") or {}).values())
            used.update((b.get("ids") or {}).values())
        used.update(self.rule_ids.values())
        while self.next_rule_id in used:
            self.next_rule_id += 1
        rid = self.next_rule_id
        self.next_rule_id += 1
        if self.next_rule_id > RULE_ID_BASE + 90000:
            self.next_rule_id = RULE_ID_BASE
        return rid

    # ---- openHop API ----
    def _api(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        url = self.cfg["openhop_url"].rstrip("/") + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cfg.get("api_key"):
            req.add_header("X-API-Key", self.cfg["api_key"])
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode() or "{}")
        self.openhop_ms = round((time.time() - t0) * 1000)
        if isinstance(res, dict) and res.get("success") is False:
            raise RuntimeError(res.get("error") or res.get("message") or "API error")
        return res

    # ---- allow-list helpers ----
    def hop_allowed(self, hop: str) -> bool:
        return any(hops_related(hop, a) for a in self.allow_hops)

    def text_allowed(self, text: str) -> bool:
        low = text.casefold()
        return any(a.casefold() in low for a in self.allow_texts if a)

    # ---- matching (mirrors the openHop rules SpamGuard writes) ----
    def hop_mode(self, b: dict) -> str:
        return b.get("match") or self.cfg.get("hop_match_mode", "contains_known")

    # ---- known people ----
    def is_known(self, name: str) -> bool:
        if name in self.allow_senders:
            return True
        v = self.known.get(name)
        return bool(v) and v[2] >= int(self.cfg.get("known_min_msgs", 1))

    def known_list(self) -> list[str]:
        """The names written to openHop for 'let known people through' (most recently heard kept)."""
        names = [k for k in self.known if self.is_known(k)]
        names = sorted(names, key=lambda k: -self.known[k][1])[:2000]
        return sorted(set(names) | {n for n in self.allow_senders if n})

    def _held_in_passing(self, e: Event) -> bool:
        """Held only because it passed THROUGH a blocked repeater partway along its route
        (spam starts at the blocked repeater itself)."""
        b = self.blocks.get(e.matched) if e.matched else None
        return bool(b and b["kind"] == "hop" and self.gated(b) and e.path and e.path[0] != b["value"])

    def learn_sender(self, e: Event, spam: bool):
        """Count a genuine message towards its sender becoming known."""
        if spam or e.random or e.obfuscated or not e.sender or e.sender == "?":
            return
        if e.matched and not self._held_in_passing(e):
            return
        for b in self.blocks.values():  # never learn from messages that START at a blocked repeater
            if b["kind"] == "hop" and e.path and e.path[0] == b["value"]:
                return
        was = self.is_known(e.sender)
        v = self.known.get(e.sender)
        if v is None:
            self.known[e.sender] = [e.ts, e.ts, 1]
        elif e.ts > v[1]:  # messages read again after a restart are older: don't count twice
            v[1] = e.ts
            v[2] += 1
        if not was and self.is_known(e.sender):
            self._important = True

    # ---- history for the overview ----
    def airtime_ms(self, length: int) -> float:
        """LoRa time on air for one packet with openHop's radio settings (0 if unknown)."""
        r = self.radio
        try:
            sf, bw, cr = int(r["spreading_factor"]), float(r["bandwidth"]), int(r["coding_rate"])
        except (KeyError, TypeError, ValueError):
            return 0.0
        if not (5 <= sf <= 12 and bw > 0 and length > 0):
            return 0.0
        cr = cr - 4 if cr > 4 else cr          # 5..8 means 4/5..4/8
        tsym = (2 ** sf) / bw * 1000
        de = 1 if tsym > 16 else 0
        pre = int(r.get("preamble_length") or 8)
        n = 8 + max(math.ceil((8 * length - 4 * sf + 28 + 16) / (4 * (sf - 2 * de))) * (cr + 4), 0)
        return (pre + 4.25 + n) * tsym

    def _people_block(self, b: Optional[dict]) -> bool:
        return bool(b) and b["kind"] in ("hop", "suffix", "links", "lockdown")

    def _count(self, e: Event):
        if e.ts <= self.hist_mark:
            return  # already counted before a restart
        self.hist_mark = e.ts
        hour = str(int(e.ts // 3600 * 3600))
        h = self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})
        h["m"] += 1
        b = self.blocks.get(e.matched) if e.matched else None
        cc = self.clusters.get(e.campaign) if e.campaign is not None else None
        spammy = e.random or e.obfuscated or bool(cc and cc.get("strong"))
        if e.matched:
            if self._people_block(b) and not spammy:
                h["g"] += 1
                return
            h["c"] += 1
            if self.cfg["mode"] == "protect" and not self.cfg.get("paused"):
                h["a"] = round(h["a"] + self.airtime_ms(e.length), 1)
        elif spammy:
            h["x"] += 1
        else:
            return
        hop = e.first_hop
        h["h"][hop] = h["h"].get(hop, 0) + 1
        if len(self.hist) > 200:
            for k in sorted(self.hist)[:-192]:
                del self.hist[k]

    def metrics(self) -> dict:
        now = time.time()
        cut24, cut7 = now - 86400, now - 7 * 86400
        def tot(cut):
            t = {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0}
            for k, v in self.hist.items():
                if int(k) >= cut - 3600:
                    for f in t:
                        t[f] += v.get(f, 0)
            spam = t["c"] + t["x"]
            t["spam"] = spam
            t["stop_rate"] = round(100 * t["c"] / spam) if spam else None
            t["spam_share"] = round(100 * spam / t["m"]) if t["m"] else None
            return t
        this_hour = int(now // 3600 * 3600)
        hourly = []
        for i in range(23, -1, -1):
            v = self.hist.get(str(this_hour - i * 3600), {})
            hourly.append({"t": this_hour - i * 3600, "c": v.get("c", 0), "x": v.get("x", 0), "m": v.get("m", 0)})
        daily = []
        for i in range(6, -1, -1):
            day0 = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)) - i * 86400
            c = x = m = 0
            for k, v in self.hist.items():
                if day0 <= int(k) < day0 + 86400:
                    c += v.get("c", 0); x += v.get("x", 0); m += v.get("m", 0)
            daily.append({"t": day0, "c": c, "x": x, "m": m})
        by_hour = [0] * 24  # spam by hour of day, last 7 days
        sources: dict[str, dict] = {}
        for k, v in self.hist.items():
            t = int(k)
            if t < cut7:
                continue
            by_hour[time.localtime(t).tm_hour] += v.get("c", 0) + v.get("x", 0)
            for hop, n in (v.get("h") or {}).items():
                s7 = sources.setdefault(hop, {"hop": hop, "d7": 0, "d1": 0, "last": 0})
                s7["d7"] += n
                if t >= cut24 - 3600:
                    s7["d1"] += n
                s7["last"] = max(s7["last"], t)
        top = sorted(sources.values(), key=lambda s: (-s["d7"], -s["d1"]))[:15]
        for s7 in top:
            s7["blocked"] = f"hop:{s7['hop']}" in self.blocks
            s7["allowed"] = self.hop_allowed(s7["hop"]) if s7["hop"] != "DIRECT" else False
            s7["candidates"] = self.repeaters_for(s7["hop"])
        return {"d1": tot(cut24), "d7": tot(cut7), "hourly": hourly, "daily": daily, "by_hour": by_hour,
                "sources": top, "me": self.me, "radio_known": bool(self.airtime_ms(40)),
                "since": min((int(k) for k in self.hist), default=None)}

    def repeaters_for(self, hop: str) -> list:
        """Repeaters openHop has heard adverts from whose key starts with this route code.
        Short codes are shared by many repeaters, so this can be several."""
        if not hop or hop == "DIRECT":
            return []
        out = [r for r in self.repeaters["list"] if r["key"].startswith(hop)]
        return sorted(out, key=lambda r: -r["seen"])[:6]

    def refresh_openhop_info(self, force: bool = False):
        """Radio settings (for airtime) and the repeater directory (for the map), at most every 30 min."""
        now = time.time()
        if not force and now - self.repeaters["ts"] < 1800:
            return
        self.repeaters["ts"] = now
        try:
            st = self._api("GET", "/api/stats")
            st = st.get("data", st) if isinstance(st, dict) else {}
            conf = st.get("config") or {}
            self.radio = dict(conf.get("radio") or {})
            rp = conf.get("repeater") or {}
            self.me = {"name": rp.get("node_name") or st.get("site_name") or "", "hash": str(st.get("local_hash") or "").upper(),
                       "lat": rp.get("latitude"), "lon": rp.get("longitude")}
        except Exception as e:
            log.debug("openHop stats not available: %s", e)
        try:
            res = self._api("GET", "/api/adverts_by_contact_type?contact_type=Repeater&hours=336&limit=3000")
            rows = res.get("data", []) if isinstance(res, dict) else []
            seen: dict[str, dict] = {}
            for r in rows:
                key = str(r.get("pubkey") or "").upper()
                if not key:
                    continue
                prev = seen.get(key)
                ts = float(r.get("last_seen") or r.get("timestamp") or 0)
                lat, lon = r.get("latitude"), r.get("longitude")
                ok = isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and (lat or lon)
                if prev is None or ts > prev["seen"]:
                    seen[key] = {"key": key, "name": r.get("node_name") or "", "seen": ts,
                                 "lat": lat if ok else (prev or {}).get("lat"), "lon": lon if ok else (prev or {}).get("lon")}
            self.repeaters["list"] = list(seen.values())
        except Exception as e:
            log.debug("openHop repeater list not available: %s", e)

    def _spammy(self, e: Event) -> bool:
        cc = self.clusters.get(e.campaign) if e.campaign is not None else None
        matched = bool(e.matched) and not self._held_in_passing(e)
        return e.random or e.obfuscated or matched or bool(cc and cc.get("suspect"))

    def forget_old_names(self):
        horizon = time.time() - int(self.cfg.get("known_days", 30)) * 86400
        for k in [k for k, v in self.known.items() if v[1] < horizon]:
            del self.known[k]
        if len(self.known) > 5000:  # keep the 5,000 most recently heard
            self.known = dict(sorted(self.known.items(), key=lambda kv: -kv[1][1])[:5000])

    def gated(self, b: dict) -> bool:
        """Blocks that let known people through (written after the 'known people' rule)."""
        return b["kind"] in ("links", "lockdown") or (b["kind"] == "hop" and self.hop_mode(b) == "contains_known")

    def block_matches(self, b: dict, e: Event) -> bool:
        if self.gated(b) and self.is_known(e.sender):
            return False
        if b["kind"] == "lockdown":
            return True
        if b["kind"] == "links":
            return any(w in e.text for w in b["value"])
        if b["kind"] == "hop":
            if self.hop_mode(b) in ("contains", "contains_known"):
                return b["value"] in e.path
            return ">".join(e.path) in (b.get("paths") or {})
        if b.get("sender") and e.sender == b["sender"]:
            return False  # the original sender may re-send their own message
        if b["kind"] == "words":
            return all(w in e.text for w in b["value"])
        if b["kind"] == "suffix":
            suf = b["value"]
            return (len(e.path) == len(suf) + 1 and all(h in e.path for h in suf)
                    and e.first_hop not in self.allowed_origins(b))
        return b["value"] in e.text

    def _match_event(self, e: Event, count: bool = True):
        # Same order openHop checks the rules in (see build_rules).
        rank = {"manual": 0, "hop": 1, "campaign": 2, "dedupe": 3, "rotation": 9}
        for key, b in sorted(self.blocks.items(), key=lambda kv: (10 if self.gated(kv[1]) else rank.get(kv[1].get("source"), 2),
                                                                   -kv[1]["created"])):
            if e.ts >= b["created"] - 1 and self.block_matches(b, e):
                e.matched = key
                if count:
                    b["hits"] = b.get("hits", 0) + 1
                    b["last_hit"] = e.ts
                    self.stats["caught"] += 1
                    self.catches.append(e.ts)
                return

    # ---- ingest ----
    def ingest(self, packets: list[dict]) -> int:
        now = time.time()
        new = 0
        for p in sorted(packets, key=lambda x: x.get("timestamp") or 0):
            try:
                if int(p.get("type", -1)) != PAYLOAD_TYPE_GRP_TXT:
                    continue
            except (TypeError, ValueError):
                continue
            key = str(p.get("packet_hash") or p.get("id"))
            if key in self.seen_packets:
                continue
            self.seen_packets[key] = now
            try:
                payload = bytes.fromhex(p.get("payload") or "")
            except ValueError:
                continue
            dec = decrypt_group_text(payload, self.cfg["channels"])
            self.stats["channel_messages"] += 1
            if not dec:
                self.stats["unreadable"] += 1
                continue
            ts = float(p.get("timestamp") or now)
            e = Event(ts, parse_path(p.get("original_path")), dec["sender"] or "?", dec["text"], dec["channel"])
            e.packet = str(p.get("packet_hash") or "")
            try:
                e.length = int(p.get("length") or 0) or len(payload) + 2 + len(e.path) * max(1, len((e.path or ["00"])[0]) // 2)
            except (TypeError, ValueError):
                e.length = len(payload)
            e.seen_at = now
            e.exempt = self.text_allowed(e.text)
            trusted = e.sender in self.allow_senders
            e.name_score = name_score(e.sender, self.name_res)
            e.random = not trusted and (e.name_score >= self.cfg["name_score_threshold"] or e.obfuscated)
            h = self.sender_history.setdefault(e.sender, {"first": ts, "count": 0, "hops": set()})
            if trusted and e.first_hop not in h["hops"] and h["hops"] and not any(
                    hops_related(e.first_hop, x) for x in h["hops"]):
                self.note(f"Trusted name '{e.sender}' arrived from a new place (first hop {e.first_hop}) - "
                          "names can be faked, so check this is really them")
            again = key in self.counted_packets  # read again after a restart: don't count it twice
            if not again:
                h["count"] += 1
                self.counted_packets[key] = None
                while len(self.counted_packets) > 3000:
                    self.counted_packets.popitem(last=False)
            h["hops"].add(e.first_hop)
            self._match_event(e, count=not again)
            b = self.blocks.get(e.matched) if e.matched else None
            # Only blocks that hold PEOPLE back (repeater, route, link, lockdown), not spam-text blocks
            if b and not again and b["kind"] in ("hop", "suffix", "links", "lockdown") \
                    and not e.random and not e.obfuscated:
                self.held.append({"ts": e.ts, "sender": e.sender, "text": e.text[:160], "channel": e.channel,
                                  "path": ">".join(e.path) or "direct", "matched": e.matched,
                                  "packet": e.packet, "why": self.describe(b)})
            self.events.append(e)
            new += 1
        while len(self.seen_packets) > 5000:
            self.seen_packets.popitem(last=False)
        horizon = now - max(self.cfg["long_window_seconds"], self.cfg["dedupe_seconds"], self.cfg["window_seconds"]) - 60
        while self.events and self.events[0].ts < horizon:
            self.events.popleft()
        for s in [s for s, h in self.sender_history.items() if h["first"] < now - 86400]:
            del self.sender_history[s]
        return new

    # ---- detection ----
    def _similar(self, a: frozenset, b: frozenset, th: float) -> bool:
        if not a or not b:
            return False
        small, big = (a, b) if len(a) <= len(b) else (b, a)
        if len(small) / len(big) < th * 0.5:
            return False
        inter = len(a & b)
        # containment: a spam line padded with extra words still matches its original
        return inter / len(small) >= th and inter / len(a | b) >= th * 0.6

    def find_campaigns(self, events: list[Event]) -> dict[int, dict]:
        """Group near-identical messages from different senders (survives added words, case, look-alikes).
        Incremental: each distinct message is compared with the others once, not on every check."""
        groups: dict[str, list[Event]] = {}
        for e in events[-400:]:
            if e.norm and not e.exempt and len(e.norm) >= 8:
                groups.setdefault(e.norm, []).append(e)
        th = self.cfg["similarity"] / 100.0
        cache = getattr(self, "_sim", None)
        if cache is None or cache["th"] != th:
            cache = self._sim = {"th": th, "sh": {}, "edges": {}}
        sh, edges = cache["sh"], cache["edges"]
        for k in [k for k in sh if k not in groups]:  # forget messages that left the window
            del sh[k]
            for n in edges.pop(k, ()):
                edges.get(n, set()).discard(k)
        for k in groups:
            if k in sh:
                continue
            s_k = shingles(k)
            for other, s_o in sh.items():
                if self._similar(s_k, s_o, th):
                    edges.setdefault(k, set()).add(other)
                    edges.setdefault(other, set()).add(k)
            sh[k] = s_k
        keys = list(groups)
        index = {k: i for i, k in enumerate(keys)}
        parent = list(range(len(keys)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for k, ns in edges.items():
            for n in ns:
                if k in index and n in index:
                    parent[find(index[k])] = find(index[n])
        clusters: dict[int, dict] = {}
        for i, k in enumerate(keys):
            c = clusters.setdefault(find(i), {"events": [], "senders": set(), "hops": collections.Counter()})
            for e in groups[k]:
                c["events"].append(e)
                c["senders"].add(e.sender)
                c["hops"][e.first_hop] += 1
        out = {}
        for cid, c in clusters.items():
            if len(c["senders"]) >= 2:
                for e in c["events"]:
                    e.campaign = cid
                out[cid] = c
        return out

    def analyse(self) -> dict:
        now = time.time()
        c = self.cfg
        win = [e for e in self.events if e.ts >= now - c["window_seconds"]]
        long_win = [e for e in self.events if e.ts >= now - c["long_window_seconds"]]
        for e in long_win:
            e.campaign = None
        campaigns = self.find_campaigns(long_win)
        for cc in campaigns.values():
            # Several regulars saying the same thing ("evening all") is a conversation, not spam:
            # a campaign needs at least two senders that look made-up, disguised or brand new.
            sus = {e.sender for e in cc["events"] if self.suspect(e)}
            cc["suspect"] = len(sus) >= min(2, len(cc["senders"]))
            strong = {e.sender for e in cc["events"] if (e.random or e.obfuscated) and e.sender not in self.allow_senders}
            cc["strong"] = len(strong) >= 2
        campaign_senders = {cid: cc["senders"] for cid, cc in campaigns.items()
                            if len(cc["senders"]) >= c["text_distinct_senders"] and cc["suspect"]}
        hops: dict[str, dict] = {}

        def hop(k):
            return hops.setdefault(k, {"msgs": 0, "senders": set(), "random": set(), "new": set(),
                                       "campaign": set(), "random_long": set(), "caught": 0})

        for e in long_win:
            if e.random:
                hop(e.first_hop)["random_long"].add(e.sender)
        for e in win:
            h = hop(e.first_hop)
            h["msgs"] += 1
            h["senders"].add(e.sender)
            if e.matched:
                h["caught"] += 1
            if e.random:
                h["random"].add(e.sender)
            hist = self.sender_history.get(e.sender, {"first": e.ts, "count": 1})
            if (hist["count"] <= 2 and hist["first"] >= now - c["window_seconds"]
                    and e.sender not in self.allow_senders):
                h["new"].add(e.sender)
            if e.campaign in campaign_senders:
                h["campaign"].add(e.sender)
        return {"window": win, "long": long_win, "hops": hops, "campaigns": campaigns}

    def suspect(self, e: Event) -> bool:
        if e.sender in self.allow_senders:
            return False
        if e.random or e.obfuscated:
            return True
        h = self.sender_history.get(e.sender)
        return h is None or h["count"] <= 2

    @staticmethod
    def _rule_text(common: Optional[str], originals: list[str], minimum: int = 14) -> Optional[str]:
        """Shared text worked out with mentions removed: keep one unbroken piece that really
        appears in every message, so the openHop 'contains' rule matches them."""
        if not common:
            return None
        piece = longest_piece(common)
        ok = weighted_len(piece) >= minimum and all(piece in t for t in originals)
        return piece if ok else None

    def hop_signals(self, h: dict) -> list[str]:
        c = self.cfg
        why = []
        if len(h["random"]) >= c["hop_random_senders"]:
            why.append(f"{len(h['random'])} random-looking names")
        if len(h["new"]) >= c["hop_new_senders"]:
            why.append(f"{len(h['new'])} brand-new names")
        if len(h["campaign"]) >= c["hop_campaign_senders"]:
            why.append(f"{len(h['campaign'])} names sending the same spam")
        if len(h["random_long"]) >= c["hop_random_senders_long"]:
            why.append(f"{len(h['random_long'])} random names over {round(c['long_window_seconds'] / 3600, 1)} h")
        return why

    def _add_block(self, key, kind, value, reason, source, channel=None, ttl=None, from_ts=None,
                   action=None, match=None, sender=None) -> bool:
        now = time.time()
        expires = (from_ts or now) + (ttl or self.cfg["block_ttl_seconds"])
        if expires <= now:
            return False
        b = self.blocks.get(key)
        if b is None:
            self.blocks[key] = {"id": self._new_id(), "kind": kind, "value": value, "channel": channel,
                                "reason": reason, "source": source, "created": now, "expires": expires,
                                "hits": 0, "last_hit": None, "action": action, "match": match,
                                "manual": source == "manual", "sender": sender}
            if kind == "hop":
                self.blocks[key]["paths"] = {}
            if kind == "suffix":
                self.blocks[key]["user_allowed"] = []
                self.blocks[key]["allow_ids"] = {}
            self.note(f"Started blocking {self.describe(self.blocks[key])}: {reason[0].lower() + reason[1:]}",
                      journal=source != "dedupe")
            if source != "dedupe":
                self._important = True
            nb = self.blocks[key]
            self.ev({"type": "block", "event": "start", "key": key, "kind": kind, "value": value,
                     "source": source, "reason": reason, "exempt_sender": sender})
            return True
        if expires >= b["expires"]:
            b["expires"] = expires
            if b.get("source") != "manual":
                b["reason"] = reason
            # A dedupe rule that turns out to be a campaign is promoted (longer life).
            if source == "campaign" and b.get("source") == "dedupe":
                b["source"] = "campaign"
                b["sender"] = None  # a campaign has no "original sender" to let through
        return False

    def describe(self, b: dict) -> str:
        if b["kind"] == "hop":
            m = self.hop_mode(b)
            if m == "contains_known":
                return f"anything via repeater {b['value']}, except people it knows"
            how = "messages starting at" if m == "exact_paths" else "anything via"
            return f"{how} repeater {b['value']}"
        if b["kind"] == "links":
            return "links from names SpamGuard doesn't know"
        if b["kind"] == "lockdown":
            return "lockdown: channel messages from names SpamGuard doesn't know"
        if b["kind"] == "suffix":
            route = ">".join(b["value"])
            return (f"new repeaters sending via {route}" if route
                    else "new repeaters right next to yours")
        but = f" (except from {b['sender']})" if b.get("sender") else ""
        if b["kind"] == "words":
            return "messages containing all of " + ", ".join(f"\"{w}\"" for w in b["value"]) + but
        return f"text \"{b['value']}\"" + but

    def learn_paths(self, events) -> bool:
        added = False
        cap = int(self.cfg.get("max_paths_per_hop", 50))
        for e in events:
            if not e.path:
                continue
            b = self.blocks.get(f"hop:{e.first_hop}")
            if not b or self.hop_mode(b) != "exact_paths":
                continue
            paths = b.setdefault("paths", {})
            ps = ">".join(e.path)
            if ps in paths or ps in b.get("ignored_paths", []) or len(paths) >= cap:
                continue
            paths[ps] = self._new_id()
            self._important = True
            self.note(f"Repeater {e.first_hop}: learnt spam route {ps}")
            added = True
        return added

    # ---- learnt network shape (for identity-changing repeaters) ----
    def record_routes(self, events):
        """Remember which repeaters normally start routes (good traffic) and which ones relay."""
        now = time.time()
        for e in events:
            if e.recorded or now - e.ts < 120:  # wait until campaigns are known
                continue
            e.recorded = True
            self._count(e)
            if not e.path:  # heard directly: no route to learn, but the sender still counts
                self.learn_sender(e, self._spammy(e))
                continue
            for h in e.path[1:]:
                self.relays[h] = max(self.relays.get(h, 0), e.ts)
            spam = e.random or e.obfuscated or e.campaign is not None or (
                e.matched in self.blocks and self.blocks[e.matched].get("source") != "dedupe")
            self.learn_sender(e, self._spammy(e))
            r = self.routes.setdefault(">".join(e.path), [e.ts, e.ts, 0, 0])
            r[1] = max(r[1], e.ts)
            r[3 if spam else 2] += 1
        self.forget_old_names()
        horizon = now - self.cfg["route_memory_days"] * 86400
        if len(self.routes) > 5000 or any(v[1] < horizon for v in list(self.routes.values())[:50]):
            self.routes = {k: v for k, v in self.routes.items() if v[1] >= horizon}
            self.routes = dict(sorted(self.routes.items(), key=lambda kv: -kv[1][1])[:5000])
            self.relays = {k: v for k, v in self.relays.items() if v >= horizon}

    def known_origin(self, hop: str) -> bool:
        """A repeater with a genuine history: it relays other traffic, or has sent normal messages."""
        if self.hop_allowed(hop) or hop in self.relays:
            return True
        good = sum(v[2] for k, v in self.routes.items() if k.split(">", 1)[0] == hop)
        return good >= 2

    def allowed_origins(self, b: dict) -> set:
        """Known repeaters that have sent genuine traffic along this route (plus any you allowed)."""
        suf = ">".join(b["value"])
        out = set(b.get("user_allowed", []))
        for k, v in self.routes.items():
            first, _, rest = k.partition(">")
            if rest == suf and v[2] > 0 and self.known_origin(first):
                out.add(first)
        return out

    def rotation_candidates(self, window) -> dict:
        """Routes receiving spam from several never-seen first repeaters."""
        out: dict[tuple, dict] = {}
        for e in window:
            if not e.path or self.known_origin(e.first_hop):
                continue
            if not (e.random or e.obfuscated or e.campaign is not None):
                continue
            d = out.setdefault(tuple(e.path[1:]), {"origins": set(), "senders": set()})
            d["origins"].add(e.first_hop)
            d["senders"].add(e.sender)
        return out

    def decide(self) -> bool:
        c = self.cfg
        now = time.time()
        a = self.analyse()
        self.clusters = a["campaigns"]
        changed = False

        def want(key, kind, value, reason, source, channel=None, ttl=None, from_ts=None, sender=None):
            nonlocal changed
            if self.suppressed.get(key, 0) > now:
                return
            if self._add_block(key, kind, value, reason, source, channel, ttl, from_ts, sender=sender):
                changed = True

        # 1. Spam campaigns: same/similar text from several names -> block the shared text.
        if c.get("enable_text_rules", True):
            for cc in a["campaigns"].values():
                if len(cc["senders"]) < c["text_distinct_senders"] or not cc.get("suspect"):
                    continue
                originals = list(dict.fromkeys(e.text for e in cc["events"]))
                raws = [strip_mentions(t) for t in originals]
                last = max(e.ts for e in cc["events"])
                common = self._rule_text(common_substring(raws, c["min_rule_chars"]), originals, c["min_rule_chars"])
                ws = common_words(raws, c["min_rule_chars"]) if len(raws) > 1 else None
                long_ttl = int(c.get("spam_text_days", 0) * 86400) if cc.get("strong") else 0
                ttl = max(long_ttl, c["block_ttl_seconds"]) if long_ttl else None
                if common:
                    want(text_key(common), "text", common,
                         f"Sent under {len(cc['senders'])} different names", "campaign",
                         channel=cc["events"][-1].channel, from_ts=last, ttl=ttl)
                if ws and (not common or len(common) < 0.6 * len(strip_emoji(raws[-1]))):
                    # Copies differ: also match on shared words, which survives emoji moving around.
                    want("words:" + hashlib.sha1("|".join(ws).encode()).hexdigest()[:10], "words", ws,
                         f"Sent under {len(cc['senders'])} different names, with small changes",
                         "campaign", channel=cc["events"][-1].channel, from_ts=last, ttl=ttl)
                if not common and not ws and cc.get("strong"):
                    # Variants share no usable text (heavy obfuscation): block each variant seen.
                    # Only when made-up or disguised names are involved: short everyday messages
                    # ("evening all") are often similar without sharing text.
                    for raw in raws[-5:]:
                        snip = middle_chunk(longest_piece(raw), c["text_rule_chars"])
                        if weighted_len(snip) >= c["min_rule_chars"]:
                            want(text_key(snip), "text", snip, "Variant of a spam campaign", "campaign",
                                 channel=cc["events"][-1].channel, from_ts=last)

        # 2. Duplicate suppression: the first copy gets through, repeats do not.
        if c.get("dedupe_enabled", False):
            variants: dict[str, dict] = {}
            for e in a["long"]:
                if e.ts >= now - c["dedupe_seconds"] and not e.exempt and e.sender not in self.allow_senders \
                        and len(e.norm) >= c["dedupe_min_chars"] * 0.6:
                    v = variants.setdefault(e.norm, {"raws": set(), "last": 0, "ch": e.channel, "senders": set()})
                    v["raws"].add(e.text)
                    v["senders"].add(e.sender)
                    v["last"] = max(v["last"], e.ts)
            for norm, v in variants.items():
                if len(v["raws"]) < 2:
                    continue
                originals = sorted(v["raws"])
                raws = [strip_mentions(t) for t in originals]
                only = next(iter(v["senders"])) if len(v["senders"]) == 1 else None  # one person editing their own message
                common = self._rule_text(common_substring(raws, c["min_rule_chars"]), originals, c["min_rule_chars"])
                if common:
                    want(text_key(common), "text", common, "Re-sent with small changes", "dedupe",
                         channel=v["ch"], ttl=c["dedupe_seconds"], from_ts=v["last"], sender=only)
                ws = common_words(raws, c["min_rule_chars"])
                if ws and (not common or len(common) < 0.6 * len(strip_emoji(raws[-1]))):
                    want("words:" + hashlib.sha1("|".join(ws).encode()).hexdigest()[:10], "words", ws,
                         "Re-sent with emoji or symbols changed", "dedupe",
                         channel=v["ch"], ttl=c["dedupe_seconds"], from_ts=v["last"], sender=only)
            # Oldest first, so the rule remembers who sent the message originally.
            first: dict[str, Event] = {}
            last: dict[str, float] = {}
            for e in a["long"]:
                if e.ts < now - c["dedupe_seconds"]:
                    continue
                content = longest_piece(strip_mentions(e.text))
                if e.exempt or e.sender in self.allow_senders or len(content) < c["dedupe_min_chars"]:
                    continue
                snip = middle_chunk(content, c["text_rule_chars"])
                if len(snip) < c["min_rule_chars"]:
                    continue
                first.setdefault(snip, e)
                last[snip] = e.ts
            for snip, e in first.items():
                want(text_key(snip), "text", snip, "Copies under other names are blocked", "dedupe",
                     channel=e.channel, ttl=c["dedupe_seconds"], from_ts=last[snip], sender=e.sender)

        # 3. Source repeater blocking.
        if c.get("enable_hop_rules", True):
            for hop, h in a["hops"].items():
                if hop == "DIRECT" or self.hop_allowed(hop):
                    continue
                why = self.hop_signals(h)
                if why:
                    reason = why[0][0].upper() + why[0][1:] + (f" (and {len(why) - 1} other sign{'s' if len(why) > 2 else ''})" if len(why) > 1 else "")
                    want(f"hop:{hop}", "hop", hop, reason, "hop", ttl=int(c.get("hop_block_ttl_seconds", 7200)))

        if self.learn_paths(a["long"]):
            changed = True

        # 4. A spammer whose repeater keeps changing identity: unknown first repeaters, same onward route.
        self.record_routes(a["long"])
        self.log_messages(a["long"])
        if self.evidence is not None:
            self.evidence.flush(keep_days=c["evidence_days"])
        if c.get("enable_rotation_guard", True):
            linked = set()
            for b in self.blocks.values():
                if b["kind"] == "hop":
                    linked |= {tuple(p.split(">")[1:]) for p in (b.get("paths") or {})}
            for suf, d in self.rotation_candidates(a["window"]).items():
                need = 2 if suf in linked else c["rotate_first_hops"]
                if len(d["origins"]) >= need and len(d["senders"]) >= 2:
                    route = ">".join(suf)
                    where = f"via {route}" if suf else "directly next to your repeater"
                    want(f"suffix:{route}", "suffix", list(suf),
                         f"{len(d['origins'])} never-seen repeaters sent spam {where}"
                         + (" (same route as a blocked spam repeater)" if suf in linked else ""), "rotation")
            # A trusted person heard through a blocked route: let their repeater through.
            for e in a["window"]:
                if e.sender in self.allow_senders and e.path:
                    b = self.blocks.get("suffix:" + ">".join(e.path[1:]))
                    if b and e.first_hop not in b.setdefault("user_allowed", []):
                        b["user_allowed"].append(e.first_hop)
                        self._important = True
                        self.note(f"Let repeater {e.first_hop} through on route {'>'.join(e.path[1:]) or '(direct)'} "
                                  f"because trusted '{e.sender}' uses it")
                        changed = True

        # 5. Links from names SpamGuard doesn't know.
        hl = c.get("hold_links", "campaign")
        cur = self.blocks.get("links:new")
        if cur and cur.get("source") == "links" and cur.get("links_mode") != hl:
            self.blocks.pop("links:new")  # setting changed: start again under the new setting
            changed = True
        if hl == "always":
            want("links:new", "links", ["http", "www."], "Links are always held unless the sender is known", "links",
                 ttl=PERMANENT_SECONDS)
        elif hl == "campaign":
            busy = [max(b["created"], b.get("last_hit") or 0) for b in self.blocks.values()
                    if b.get("source") == "campaign" and b["kind"] in ("text", "words")]
            latest = max(busy, default=0)
            if latest > now - 3600:
                want("links:new", "links", ["http", "www."],
                     "A spam campaign is under way, so links are held unless the sender is known", "links",
                     ttl=3600, from_ts=latest)
        if "links:new" in self.blocks:
            self.blocks["links:new"].setdefault("links_mode", hl)

        for k in [k for k, b in self.blocks.items() if b["expires"] <= now]:
            b = self.blocks.pop(k)
            if b.get("source") != "dedupe":
                self._important = True
                self.note(f"Stopped blocking {self.describe(b)} (expired after {b.get('hits', 0)} catches)")
            changed = True
        for k in [k for k, v in self.suppressed.items() if v <= now]:
            del self.suppressed[k]
        self._save_state(force=self._important)
        return changed

    # ---- policy sync ----
    def rule_action(self, b: dict) -> str:
        a = b.get("action") or ("drop" if self.cfg["mode"] == "protect" else "log_only")
        return "drop" if a == "drop" else "log_only"

    def build_rules(self) -> list[dict]:
        main, tail = self.build_rule_sets()
        return main + tail

    def build_rule_sets(self) -> tuple[list[dict], list[dict]]:
        """(rules placed before your own openHop rules, rules placed after them).
        Rotation blocks contain 'allow' exceptions, so they go after your rules and never
        override anything you have set up yourself."""
        if self.cfg.get("paused"):
            return [], []
        tail: list[dict] = []
        for key, b in sorted(self.blocks.items(), key=lambda kv: kv[1]["id"]):
            if b["kind"] != "suffix":
                continue
            suf = b["value"]
            ids = b.setdefault("allow_ids", {})
            for o in sorted(self.allowed_origins(b))[: int(self.cfg["max_origins_per_route"])]:
                if o not in ids:
                    ids[o] = self._new_id()
                tail.append({"id": ids[o], "name": f"{RULE_PREFIX}{key}:allow:{o}", "enabled": True,
                             "if": {"all": [
                                 {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                 {"field": "path_hashes", "op": "equals", "value": [o] + suf}]},
                             "then": {"action": "allow"}})
            tail.append({"id": b["id"], "name": f"{RULE_PREFIX}{key}", "enabled": True,
                         "if": {"all": [
                             {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                             {"field": "hop_count", "op": "equals", "value": len(suf) + 1}]
                             + [{"field": "path_hashes", "op": "contains", "value": h} for h in suf]},
                         "then": {"action": self.rule_action(b)}})
        return self._build_main(), tail + self._build_gated()

    def _rid(self, key: str) -> int:
        if key not in self.rule_ids:
            self.rule_ids[key] = self._new_id()
        return self.rule_ids[key]

    def _build_gated(self) -> list[dict]:
        """Blocks that let known people through: first one 'allow' rule per channel for names on
        SpamGuard's known list (an openHop object), then the blocks themselves. openHop stops at the
        first rule that matches, so a known name never reaches the blocks below it."""
        gated = sorted(((k, b) for k, b in self.blocks.items() if self.gated(b)), key=lambda kv: kv[1]["id"])
        if not gated:
            return []
        rules: list[dict] = []
        chans = sorted(self.cfg["channels"].items())
        for name, secret in chans:
            rules.append({"id": self._rid(f"known:{name}"), "name": f"{RULE_PREFIX}known-people:{name}", "enabled": True,
                          "if": {"all": [
                              {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                              {"field": "channel_hash", "op": "equals", "value": secret},
                              {"field": "channel_sender", "op": "in", "value": "@spamguard.known_senders"}]},
                          "then": {"action": "allow"}})
        for key, b in gated:
            ids = b.setdefault("ids", {})
            for name, secret in chans:
                base = [{"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                        {"field": "channel_hash", "op": "equals", "value": secret}]
                if b["kind"] == "links":
                    conds = [(w, [{"field": "channel_message_body", "op": "contains", "value": w}]) for w in b["value"]]
                elif b["kind"] == "hop":
                    conds = [("", [{"field": "path_hashes", "op": "contains", "value": b["value"]}])]
                else:  # lockdown
                    conds = [("", [])]
                for sub, extra in conds:
                    rk = f"{name}|{sub}"
                    if rk not in ids:
                        ids[rk] = self._new_id()
                    rules.append({"id": ids[rk], "name": f"{RULE_PREFIX}{key}:{name}" + (f":{sub}" if sub else ""),
                                  "enabled": True, "if": {"all": base + extra},
                                  "then": {"action": self.rule_action(b)}})
        return rules

    def _build_main(self) -> list[dict]:
        rank = {"manual": 0, "hop": 1, "campaign": 2, "dedupe": 3}
        order = sorted(((k, b) for k, b in self.blocks.items() if b["kind"] != "suffix" and not self.gated(b)),
                       key=lambda kv: (rank.get(kv[1].get("source"), 2), -kv[1]["created"]))
        rules: list[dict] = []
        limit = int(self.cfg["max_total_rules"])
        for key, b in order:
            if len(rules) >= limit:
                break
            if b["kind"] == "hop" and self.hop_mode(b) == "exact_paths":
                for ps, pid in sorted((b.get("paths") or {}).items(), key=lambda kv: kv[1]):
                    rules.append({"id": pid, "name": f"{RULE_PREFIX}{key}:{ps}", "enabled": True,
                                  "if": {"all": [
                                      {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                      {"field": "path_hashes", "op": "equals", "value": ps.split(">")}]},
                                  "then": {"action": self.rule_action(b)}})
                continue
            if b["kind"] == "hop":
                cond = {"all": [
                    {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                    {"field": "path_hashes", "op": "contains", "value": b["value"]}]}
            elif b["kind"] == "words":
                secret = self.cfg["channels"].get(b.get("channel") or "", PUBLIC_CHANNEL_KEY)
                cond = {"all": [
                    {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                    {"field": "channel_hash", "op": "equals", "value": secret}]
                    + [{"field": "channel_message_body", "op": "contains", "value": w} for w in b["value"]]}
            else:
                secret = self.cfg["channels"].get(b.get("channel") or "", PUBLIC_CHANNEL_KEY)
                cond = {"all": [
                    {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                    {"field": "channel_hash", "op": "equals", "value": secret},
                    {"field": "channel_message_body", "op": "contains", "value": b["value"]}]}
            if b["kind"] in ("text", "words") and b.get("sender"):
                cond["all"].append({"field": "channel_sender", "op": "not_equals", "value": b["sender"]})
            rules.append({"id": b["id"], "name": f"{RULE_PREFIX}{key}", "enabled": True,
                          "if": cond, "then": {"action": self.rule_action(b)}})
        if len(rules) >= limit and not self.stats.get("rule_limit_warned"):
            self.stats["rule_limit_warned"] = 1
            self.note(f"Rule limit ({limit}) reached - oldest duplicate rules were left out")
        return rules[:limit]

    def sync_policy(self, force: bool = False) -> bool:
        res = self._api("GET", "/api/policy")
        data = res.get("data", res)
        pe = dict(data.get("policy_engine") or {})
        existing = [r for r in (pe.get("rules") or []) if isinstance(r, dict)]
        user_rules = [r for r in existing if not str(r.get("name", "")).startswith(RULE_PREFIX)]
        ours_now = [r for r in existing if str(r.get("name", "")).startswith(RULE_PREFIX)]
        self.rules_seen = len(ours_now)
        main, tail = self.build_rule_sets()
        ours_new = main + tail
        needs_enable = bool(ours_new) and not pe.get("enabled")
        # The known-people list lives in openHop as an object (@spamguard.known_senders).
        objects = dict(pe.get("objects") or {}) if isinstance(pe.get("objects"), dict) else {}
        obj_now = objects.get("spamguard")
        obj_new = {"known_senders": self.known_list()} if any(
            r.get("then", {}).get("action") == "allow" and "known-people" in str(r.get("name")) for r in tail) else None
        if obj_new is None:
            objects.pop("spamguard", None)
        else:
            objects["spamguard"] = obj_new
        pe["objects"] = objects
        if not force and not needs_enable and obj_now == obj_new \
                and json.dumps(ours_now, sort_keys=True) == json.dumps(ours_new, sort_keys=True):
            self.sync_pending = False
            return False
        if not force and self.rules_expected is not None and len(ours_now) != self.rules_expected:
            self.self_heals += 1
            self.note(f"openHop had {len(ours_now)} SpamGuard rules instead of {self.rules_expected} - put them back")
        pe["rules"] = main + user_rules + tail
        if ours_new:
            pe["enabled"] = True
            pe.setdefault("default_action", "allow")
        self._api("POST", "/api/policy", {"policy_engine": pe})
        self.rules_expected = self.rules_seen = len(ours_new)
        self.last_sync = time.time()
        self.sync_pending = False
        log.info("Policy synced: %d SpamGuard rule(s), %d of your own rule(s), mode=%s%s",
                 len(ours_new), len(user_rules), self.cfg["mode"], " (PAUSED)" if self.cfg.get("paused") else "")
        return True

    # ---- loop ----
    def _note_newest(self, packets):
        """Track the newest packet openHop lists (any kind): how late it is, and when it last moved."""
        newest = max((float(p.get("timestamp") or 0) for p in packets or [] if isinstance(p, dict)), default=0) or None
        if newest and (self.last_packet_ts is None or newest > self.last_packet_ts):
            if self.last_packet_ts is not None:  # a packet we haven't seen before: how old is it already?
                self.lag_samples.append((time.time(), max(0.0, time.time() - newest)))
            self.last_packet_ts = newest
            self.heard_at = time.time()
        elif self.heard_at is None:
            self.heard_at = time.time()

    def fetch_packets(self) -> list:
        """Ask openHop only for packets newer than the newest one already seen (usually a handful),
        instead of its 500 most recent every few seconds. The query is ordered and bounded by time
        only, so openHop's database answers it straight from its timestamp index. (Filtering by
        packet type in the query makes SQLite walk every channel message ever stored.) Channel
        messages are picked out here. Older openHop versions fall back to the recent packet list."""
        limit = int(self.cfg["fetch_limit"])
        if self.use_filtered is not False:
            if self.last_packet_ts is None:
                since = time.time() - self.cfg["long_window_seconds"]
            else:
                since = self.last_packet_ts - 30  # rows are saved in arrival order; small overlap for safety
            try:
                res = self._api("GET", f"/api/filtered_packets?start_timestamp={since:.3f}&limit={limit}")
                packets = res.get("data", []) if isinstance(res, dict) else res
                if self.use_filtered is None:
                    log.info("Reading only new packets from openHop")
                self.use_filtered = True
                packets = packets or []
                self._note_newest(packets)
                return packets
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
                log.info("This openHop has no filtered packet list; reading recent packets instead")
                self.use_filtered = False
        res = self._api("GET", f"/api/recent_packets?limit={limit}")
        packets = res.get("data", []) if isinstance(res, dict) else res
        self._note_newest(packets)
        return packets or []

    def poll_once(self):
        try:
            self.refresh_openhop_info()
        except Exception:
            pass
        packets = self.fetch_packets()
        with self.lock:
            self.ingest(packets)
            if self.decide():
                self.sync_pending = True
        self.last_poll_ok = time.time()
        self.last_error = None
        due = self.last_sync is None or time.time() - self.last_sync >= self.cfg["min_sync_seconds"]
        if (self.sync_pending and due) or self.last_sync is None:
            with self.lock:
                self.sync_policy(force=self.last_sync is None)
        elif time.time() - self.last_verify > 60:
            # Once a minute make sure openHop still has exactly our rules (e.g. after an openHop
            # restart, a restore, or someone editing policies) and put them back if not.
            with self.lock:
                self.sync_policy()
        if time.time() - self.last_verify > 60:
            self.last_verify = time.time()

    def run(self, stop: threading.Event):
        while not stop.is_set():
            t0 = time.time()
            try:
                self._maybe_check_update()
            except Exception:
                pass
            try:
                self.poll_once()
                self.openhop_down_since = None
            except urllib.error.HTTPError as e:
                self.errors.append(time.time())
                self.last_error = (f"openHop refused the API key (HTTP {e.code}) - check api_key in the config"
                                   if e.code in (401, 403) else f"openHop returned HTTP {e.code}")
                log.error(self.last_error)
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as e:
                self.errors.append(time.time())
                self.openhop_down_since = self.openhop_down_since or time.time()
                reason = getattr(e, "reason", None) or "no answer within 15 seconds"
                self.last_error = f"Cannot reach openHop at {self.cfg['openhop_url']} ({reason})"
                if self.last_poll_ok is None and time.time() - self.started < 180:
                    if not getattr(self, "_waiting_logged", False):
                        log.info("Waiting for openHop to start...")
                        self._waiting_logged = True
                else:
                    log.error(self.last_error)
            except Exception as e:
                self.errors.append(time.time())
                self.last_error = str(e)
                log.error("Poll failed: %s", e)
            self.poll_ms = round((time.time() - t0) * 1000)
            self.loop_beat = time.time()
            self.loop_count += 1
            # Tell systemd the loop is alive. If this stops (a hang), systemd restarts SpamGuard.
            sd_notify("WATCHDOG=1")
            stop.wait(self.cfg["poll_seconds"])

    # ---- health ----
    def health(self) -> dict:
        now = time.time()
        c = self.cfg
        sysr = system_readings(c.get("evidence_dir", "/var/lib/openhop_spamguard"))
        restarts = systemd_value("openhop-spamguard", "NRestarts")
        openhop_state = systemd_value("openhop-repeater", "ActiveState")
        watchdog = bool(os.environ.get("WATCHDOG_USEC"))
        errors_hour = sum(1 for t in self.errors if t > now - 3600)
        problems, warnings = [], []
        stale_after = max(30, c["poll_seconds"] * 3 + 20)
        if self.loop_beat is None:
            if now - self.started > 60:
                problems.append("SpamGuard has not finished a single check since it started.")
        elif now - self.loop_beat > stale_after:
            problems.append(f"SpamGuard's checking stopped {round(now - self.loop_beat)} seconds ago."
                            + (" systemd will restart it automatically." if watchdog else ""))
        if self.openhop_down_since and now - self.openhop_down_since > 120:
            problems.append(f"openHop has not answered for {round((now - self.openhop_down_since) / 60)} minutes. "
                            "Existing blocks stay in place, but nothing new is being checked.")
        elif self.last_error and "API key" in self.last_error:
            problems.append(self.last_error)
        lag = self.openhop_lag()
        if lag is not None and lag >= c.get("lag_warn_seconds", 30):
            warnings.append(f"openHop's packet list is running about {self.fmt_secs(lag)} behind real time, so SpamGuard "
                            "sees new spam that much later and a few copies get through before a block starts. "
                            "SpamGuard's own checks are quick; the delay is in openHop saving packets. "
                            "Restarting openHop clears it for a while.")
        fix = self.openhop_speed_fix()
        if fix is False:
            warnings.append("openHop's speed fix isn't in place (an openHop upgrade puts the old setting back). "
                            "Without it openHop can fall minutes behind on a small Pi. To apply it: "
                            "sudo bash /opt/openhop_spamguard/tune-openhop.sh")
        quiet = c.get("quiet_warn_minutes", 20) * 60
        if self.heard_at and self.last_error is None and now - self.heard_at > quiet and now - self.started > quiet:
            warnings.append(f"openHop hasn't reported any new packets for {round((now - self.heard_at) / 60)} minutes. "
                            "If its own packet list has stopped too, its radio may have stopped receiving: "
                            "restart openHop (sudo systemctl restart openhop-repeater).")
        if self.rules_expected is not None and self.rules_seen is not None and self.rules_seen != self.rules_expected:
            warnings.append("openHop's rules don't match SpamGuard's. They will be put back within a minute.")
        if openhop_state and openhop_state not in ("active", "reloading", "activating"):
            problems.append(f"The openHop repeater service is {openhop_state}.")
        if sysr.get("temp_c", 0) >= 80:
            problems.append(f"The Pi is very hot ({sysr['temp_c']} °C) and may be slowing down.")
        elif sysr.get("temp_c", 0) >= 70:
            warnings.append(f"The Pi is running warm ({sysr['temp_c']} °C).")
        if sysr.get("disk_free_mb", 10 ** 6) < 200:
            warnings.append(f"Only {sysr['disk_free_mb']} MB of disk space left.")
        if sysr.get("mem_avail_pct", 100) < 10:
            warnings.append(f"The Pi is low on memory ({sysr['mem_avail_pct']}% free).")
        if self.poll_ms and self.poll_ms > c["poll_seconds"] * 1000:
            warnings.append(f"Each check is taking {self.poll_ms / 1000:.1f} s, longer than the {c['poll_seconds']} s interval.")
        if errors_hour >= 20:
            warnings.append(f"{errors_hour} errors talking to openHop in the last hour.")
        if not watchdog and restarts is not None:
            warnings.append("Automatic restart-on-hang is not active. Re-run the installer to enable it.")
        state = "bad" if problems else ("warn" if warnings else "ok")
        return {"state": state, "problems": problems, "warnings": warnings,
                "uptime": round(now - self.started), "restarts": int(restarts) if (restarts or "").isdigit() else None,
                "watchdog": watchdog, "last_check": self.loop_beat, "checks": self.loop_count,
                "check_ms": self.poll_ms, "openhop_ms": self.openhop_ms, "openhop_service": openhop_state,
                "openhop_ok": self.last_error is None and self.last_poll_ok is not None,
                "rules_expected": self.rules_expected, "rules_seen": self.rules_seen, "self_heals": self.self_heals,
                "errors_hour": errors_hour, "last_error": self.last_error,
                "last_heard": self.last_packet_ts, "openhop_lag_s": None if lag is None else round(lag),
                "openhop_speed_fix": fix, **sysr}

    # ---- updates from GitHub (only installed when asked) ----
    @staticmethod
    def _vtuple(v: str) -> tuple:
        return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4])

    def _repo(self) -> str:
        r = str(self.cfg.get("update_repo") or UPDATE_REPO).strip()
        return r if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", r) and "__" not in r else ""

    def check_update(self) -> dict:
        """Ask GitHub for the newest release. Only ever reads; installing is a separate, manual step."""
        info = dict(self.update_info)
        repo = self._repo()
        info["checked"] = time.time()
        if not repo:
            info["error"] = "No update source is set (update_repo in the config file)."
            self.update_info = info
            return info
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": f"openhop-spamguard/{VERSION}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                rel = json.loads(r.read().decode("utf-8", "replace"))
            info.update({"latest": str(rel.get("tag_name") or "").lstrip("v") or None,
                         "notes": str(rel.get("body") or "")[:4000], "url": str(rel.get("html_url") or ""),
                         "error": None})
        except urllib.error.HTTPError as e:
            if e.code == 404:  # no GitHub "release" made yet: fall back to the newest version tag
                try:
                    treq = urllib.request.Request(f"https://api.github.com/repos/{repo}/tags?per_page=100",
                                                  headers={"Accept": "application/vnd.github+json",
                                                           "User-Agent": f"openhop-spamguard/{VERSION}"})
                    with urllib.request.urlopen(treq, timeout=15) as r:
                        tags = [t.get("name", "") for t in json.loads(r.read().decode("utf-8", "replace"))]
                    tags = [t for t in tags if re.fullmatch(r"v?\d+(\.\d+){1,3}", t)]
                    if tags:
                        best = max(tags, key=self._vtuple)
                        info.update({"latest": best.lstrip("v"), "notes": "", "error": None,
                                     "url": f"https://github.com/{repo}/blob/{best}/CHANGELOG.md"})
                    else:
                        info["error"] = "No versions published yet."
                except Exception:
                    info["error"] = "No versions published yet."
            else:
                # 403/429: GitHub allows 60 API calls an hour per internet address (shared by everyone
                # behind the same router or mobile network). The ordinary release page has no such limit.
                info.update(self._latest_from_web(repo, f"GitHub answered HTTP {e.code}."))
        except Exception:
            info.update(self._latest_from_web(repo, "Couldn't reach GitHub (is the Pi online?)."))
        self.update_info = info
        return info

    @staticmethod
    def _latest_from_web(repo: str, error: str) -> dict:
        """github.com/<repo>/releases/latest redirects to the newest release's page."""
        try:
            req = urllib.request.Request(f"https://github.com/{repo}/releases/latest", method="HEAD",
                                         headers={"User-Agent": f"openhop-spamguard/{VERSION}"})
            with urllib.request.urlopen(req, timeout=15) as r:
                final = r.geturl()
            m = re.search(r"/releases/tag/v?(\d+(?:\.\d+){1,3})$", final)
            if m:
                return {"latest": m.group(1), "notes": "", "url": final, "error": None}
        except Exception:
            pass
        return {"error": error}

    def _maybe_check_update(self):
        if self.cfg.get("update_check", "daily") != "daily" or self._update_checking:
            return
        last = self.update_info.get("checked")
        if (last and time.time() - last < 86400) or time.time() - self.started < 120:
            return
        self._update_checking = True

        def go():
            try:
                self.check_update()
            finally:
                self._update_checking = False
        threading.Thread(target=go, daemon=True).start()

    def update_status(self) -> dict:
        folder = os.path.dirname(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])
        out = {}
        try:
            with open(os.path.join(folder, "update-status.json")) as f:
                out = json.load(f)
        except Exception:
            pass
        out["requested"] = os.path.exists(os.path.join(folder, "update-request"))
        return out

    def update_summary(self) -> dict:
        i = self.update_info
        latest = i.get("latest")
        return {"current": VERSION, "latest": latest, "notes": i.get("notes"), "url": i.get("url"),
                "checked": i.get("checked"), "error": i.get("error"), "repo": self._repo(),
                "available": bool(latest) and self._vtuple(latest) > self._vtuple(VERSION),
                "auto_check": self.cfg.get("update_check", "daily") == "daily",
                "installer_ready": os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"),
                "status": self.update_status()}

    def update_action(self, op: str, body: dict) -> dict:
        if op == "check_update":
            info = self.check_update()
            if info.get("error"):
                return {"ok": False, "message": info["error"]}
            s = self.update_summary()
            return {"ok": True, "message": f"Version {s['latest']} is available." if s["available"]
                    else f"You have the latest version ({VERSION})."}
        # install_update: hand the request to the root-owned updater (see update.sh)
        want = str(body.get("version") or self.update_info.get("latest") or "").lstrip("v")
        if not re.fullmatch(r"\d+(\.\d+){1,3}", want):
            raise ValueError("Press Check first, so SpamGuard knows which version to install.")
        if not os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"):
            raise ValueError("The updater isn't set up on this Pi yet. Run the installer once by hand: sudo bash install.sh")
        folder = os.path.dirname(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])
        tmp = os.path.join(folder, "update-request.tmp")
        with open(tmp, "w") as f:
            json.dump({"version": "v" + want, "asked": time.time()}, f)
        os.replace(tmp, os.path.join(folder, "update-request"))
        self.note(f"Update to v{want} requested from the web page")
        return {"ok": True, "message": f"Updating to v{want}. SpamGuard restarts in a minute or two; this page reconnects by itself."}

    def openhop_speed_fix(self) -> Optional[bool]:
        """True/False if openHop's packet-count speed fix is in place, None if not applicable.
        Re-read every few minutes, because an openHop upgrade quietly undoes it."""
        now = time.time()
        cached = getattr(self, "_fix_cache", None)
        if cached and now - cached[0] < 300:
            return cached[1]
        result = None
        try:
            import glob
            for path in glob.glob(self.cfg.get("openhop_dir", "/opt/openhop_repeater") + "/**/repeater/data_acquisition/sqlite_handler.py",
                                  recursive=True)[:1]:
                with open(path, encoding="utf-8", errors="replace") as f:
                    m = re.search(r"_cumulative_counts_ttl_sec = ([0-9.]+)", f.read())
                if m:
                    result = float(m.group(1)) > 3.0
        except Exception:
            result = None
        self._fix_cache = (now, result)
        return result

    def openhop_lag(self) -> Optional[float]:
        """Median delay over the last 10 minutes between a packet arriving and openHop listing it."""
        now = time.time()
        recent = sorted(v for t, v in self.lag_samples if t > now - 600)
        return recent[len(recent) // 2] if len(recent) >= 3 else None

    @staticmethod
    def fmt_secs(s: float) -> str:
        return f"{round(s)} seconds" if s < 90 else f"{round(s / 60)} minutes"

    # ---- status for the web page ----
    def status(self) -> dict:
        with self.lock:
            now = time.time()
            a = self.analyse()
            c = self.cfg
            hops = []
            for k, v in a["hops"].items():
                hops.append({"hop": k, "messages": v["msgs"], "senders": len(v["senders"]),
                             "random": len(v["random"]), "new": len(v["new"]), "campaign": len(v["campaign"]),
                             "random_long": len(v["random_long"]), "caught": v["caught"],
                             "blocked": f"hop:{k}" in self.blocks, "allowed": self.hop_allowed(k),
                             "signals": self.hop_signals(v)})
            hops.sort(key=lambda x: (-x["caught"] - x["random"] * 3, -x["messages"]))
            direct = next((h for h in hops if h["hop"] == "DIRECT" and h["signals"]), None)
            campaigns = []
            for cid, cc in sorted(a["campaigns"].items(), key=lambda kv: -len(kv[1]["senders"])):
                campaigns.append({"senders": len(cc["senders"]), "count": len(cc["events"]),
                                  "example": cc["events"][-1].text[:120],
                                  "variants": len({e.text for e in cc["events"]}),
                                  "hops": dict(cc["hops"].most_common(6))})
            recent = []
            for e in list(a["long"])[-80:][::-1]:
                recent.append({"ts": e.ts, "time": time.strftime("%H:%M:%S", time.localtime(e.ts)),
                               "path": ">".join(e.path) or "direct", "first_hop": e.first_hop,
                               "sender": e.sender, "text": e.text[:160], "channel": e.channel,
                               "random": e.random, "name_score": e.name_score, "obfuscated": e.obfuscated,
                               "trusted": e.sender in self.allow_senders, "campaign": e.campaign is not None,
                               "matched": e.matched, "packet": e.packet,
                               "matched_desc": self.describe(self.blocks[e.matched]) if e.matched in self.blocks else None})
            blocks = []
            rank = {"lockdown": -1, "manual": 0, "hop": 1, "rotation": 1, "links": 1, "campaign": 2, "dedupe": 3}
            for k, b in sorted(self.blocks.items(), key=lambda kv: (rank.get(kv[1].get("source"), 2), -kv[1].get("hits", 0))):
                blocks.append({"key": k, "kind": b["kind"], "value": b["value"], "source": b.get("source"),
                               "reason": b.get("reason"), "hits": b.get("hits", 0), "last_hit": b.get("last_hit"),
                               "created": b["created"], "expires_in": round(b["expires"] - now),
                               "permanent": b["expires"] - now > PERMANENT_SECONDS / 2,
                               "action": b.get("action"), "effective": "paused" if c.get("paused") else self.rule_action(b),
                               "match": b.get("match"), "mode": self.hop_mode(b) if b["kind"] == "hop" else None,
                               "sender": b.get("sender"),
                               "paths": sorted(b.get("paths") or {}) if b["kind"] == "hop" else None,
                               "allowed": sorted(self.allowed_origins(b)) if b["kind"] == "suffix" else None,
                               "user_allowed": b.get("user_allowed") if b["kind"] == "suffix" else None,
                               "unknown_seen": sorted({e.first_hop for e in a["window"] if b["kind"] == "suffix"
                                                       and e.path and tuple(e.path[1:]) == tuple(b["value"])
                                                       and e.first_hop not in self.allowed_origins(b)}) if b["kind"] == "suffix" else None,
                               "describe": self.describe(b)})
            caught_24h = sum(1 for t in self.catches if t > now - 86400)
            by_hour = [0] * 24  # index 23 = the most recent hour
            for t in self.catches:
                age = int((now - t) // 3600)
                if 0 <= age < 24:
                    by_hour[23 - age] += 1
            last_catch = max(self.catches) if self.catches else None
            settings = {m["key"]: c.get(m["key"]) for m in SETTINGS_META}
            return {
                "version": VERSION,
                "mode": c["mode"], "paused": bool(c.get("paused")), "sensitivity": c["sensitivity"],
                "service": self.health(),
                "health": {"ok": self.last_error is None and self.last_poll_ok is not None,
                           "error": self.last_error, "last_poll": self.last_poll_ok, "last_sync": self.last_sync},
                "summary": {"caught_24h": caught_24h, "last_catch": last_catch, "by_hour": by_hour,
                            "active_blocks": sum(1 for b in blocks if b["source"] != "dedupe"),
                            "dedupe_rules": sum(1 for b in blocks if b["source"] == "dedupe"),
                            "rules_written": 0 if c.get("paused") else len(self.build_rules()),
                            "channel_messages": self.stats.get("channel_messages", 0),
                            "unreadable": self.stats.get("unreadable", 0)},
                "direct_spam": direct,
                "settings": settings, "meta": SETTINGS_META, "presets": PRESETS,
                "overridden": sorted(k for k in self.settings if k in META_BY_KEY),
                "channels": sorted(c["channels"]),
                "blocks": blocks, "hops": hops[:40], "campaigns": campaigns[:15], "recent": recent,
                "evidence": dict(self.evidence.summary(), enabled=True) if self.evidence else
                            {"enabled": False, **EvidenceLog(c["evidence_dir"]).summary()},
                "known": {"count": len(self.known_list()), "min_msgs": int(c.get("known_min_msgs", 1)),
                          "learning": sum(1 for k in self.known if not self.is_known(k))},
                "metrics": self.metrics(),
                "held": [dict(h, time=time.strftime("%H:%M", time.localtime(h["ts"])))
                         for h in reversed(self.held)
                         if h["ts"] > now - 86400 and h["sender"] not in self.allow_senders and not self.is_known(h["sender"])][:20],
                "lockdown": ({"left": round(self.blocks["lockdown"]["expires"] - now)} if "lockdown" in self.blocks else None),
                "learnt": {"routes": len(self.routes), "relays": len(self.relays),
                           "origins": len({k.split(">", 1)[0] for k, v in self.routes.items() if v[2] > 0})},
                "allow": {"hops": sorted(self.allow_hops), "senders": sorted(self.allow_senders),
                          "texts": sorted(self.allow_texts)},
                "suppressed": {k: round(v - now) for k, v in self.suppressed.items()},
                "activity": [{"ts": x["ts"], "msg": x["msg"]} for x in list(self.activity)[:80]],
                "window_seconds": c["window_seconds"],
                "update": self.update_summary(),
            }

    # ---- actions from the web page ----
    def apply_settings(self, body: dict) -> dict:
        with self.lock:
            if body.get("reset"):
                self.settings = {k: v for k, v in self.settings.items() if k in EXTRA_TUNABLES}
                self.note("Advanced settings reset to defaults")
            else:
                new = {}
                for k, v in body.items():
                    if k == "mode":
                        if v not in ("monitor", "protect"):
                            raise ValueError("mode must be monitor or protect")
                    elif k == "paused":
                        v = bool(v)
                    elif k == "sensitivity":
                        if v not in PRESETS:
                            raise ValueError("sensitivity must be relaxed, balanced or strict")
                        # Choosing a preset clears hand-tuned values it controls.
                        for m in SETTINGS_META:
                            if m.get("preset"):
                                self.settings.pop(m["key"], None)
                    elif k in META_BY_KEY:
                        m = META_BY_KEY[k]
                        if m["type"] == "bool":
                            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
                        elif m["type"] == "int":
                            v = int(v)
                            if v < m.get("min", v) or v > m.get("max", v):
                                raise ValueError(f"'{m['label']}' must be between {m['min']} and {m['max']}")
                        elif m["type"] == "choice":
                            if v not in [x[0] for x in m["choices"]]:
                                raise ValueError(f"invalid choice for {m['label']}")
                        elif m["type"] == "list":
                            if isinstance(v, str):
                                v = [p.strip() for p in v.splitlines() if p.strip()]
                            for p in v:
                                try:
                                    re.compile(p)
                                except re.error as err:
                                    raise ValueError(f"pattern '{p}' is not valid: {err}")
                    else:
                        raise ValueError(f"unknown setting {k}")
                    new[k] = v
                self.settings.update(new)
                words = {"mode": {"monitor": "Monitor only", "protect": "Protect"},
                         "paused": {True: "Paused", False: "Resumed"}}
                self.note("Changed: " + ", ".join(
                    words.get(k, {}).get(v, f"{META_BY_KEY[k]['label'] if k in META_BY_KEY else k} = {v}") for k, v in new.items()))
            self.rebuild_cfg()
            self.snapshot_settings("changed on the page")
            self._save_state(force=True)
            self.sync_policy(force=True)
        return {"ok": True}

    def action(self, op: str, body: dict) -> dict:
        now = time.time()
        msg = "Done"
        with self.lock:
            if op == "unblock":
                key = body.get("key", "")
                b = self.blocks.pop(key, None)
                if b:
                    self.note(f"Removed by hand: {self.describe(b)}")
                self.suppressed[key] = now + int(body.get("suppress_seconds", 86400))
                msg = "Block removed. SpamGuard won't re-create it for 24 hours (Exceptions > Not re-blocked > Clear undoes that)."
            elif op == "lockdown":
                minutes = int(body.get("minutes") or 0)
                if minutes <= 0:
                    b = self.blocks.pop("lockdown", None)
                    if b:
                        self.note("Lockdown ended by you")
                    msg = "Lockdown ended."
                else:
                    if minutes > 24 * 60:
                        raise ValueError("A lockdown can last at most 24 hours")
                    self.blocks.pop("lockdown", None)
                    self.suppressed.pop("lockdown", None)
                    self._add_block("lockdown", "lockdown", None, f"Lockdown for {minutes} min, started by you",
                                    "lockdown", ttl=minutes * 60)
                    n = len(self.known_list())
                    msg = (f"Lockdown on for {minutes} min. Only the {n} name{'' if n == 1 else 's'} SpamGuard knows {'gets' if n == 1 else 'get'} through on the channels it reads."
                           + (" Monitor mode: nothing is actually blocked." if self.cfg["mode"] != "protect" else "")
                           + (" SpamGuard doesn't know many people yet, so most genuine users will be held too." if n < 20 else ""))
            elif op == "block_hop":
                hop = str(body.get("hop", "")).upper().strip()
                hop = hop[2:] if hop.startswith("0X") else hop
                if not HEX_HOP.fullmatch(hop):
                    raise ValueError("Enter a repeater hash of 2, 4 or 6 hex characters, e.g. 27")
                key = f"hop:{hop}"
                self.suppressed.pop(key, None)
                self.allow_hops = {a for a in self.allow_hops if not hops_related(a, hop)}
                self.blocks.pop(key, None)
                self._add_block(key, "hop", hop, "Added by you", "manual",
                                ttl=int(body.get("ttl_seconds") or self.cfg["block_ttl_seconds"]),
                                match=(body.get("match") if body.get("match") in ("exact_paths", "contains", "contains_known") else None))
                self.learn_paths(list(self.events))
                if self.hop_mode(self.blocks[key]) == "exact_paths" and not self.blocks[key]["paths"]:
                    msg = f"Blocking repeater {hop}. Routes will be learnt as its messages arrive."
            elif op in ("block_text", "mark_spam"):
                if op == "mark_spam":
                    self.ev({"type": "label", "label": "spam", "sender": body.get("sender"), "text": body.get("text"),
                             "path": body.get("path"), "packet": body.get("packet")})
                text = str(body.get("text", "")).strip()
                if op == "mark_spam":
                    text = middle_chunk(text, self.cfg["text_rule_chars"])
                if len(text) < 5:
                    raise ValueError("The text must be at least 5 characters")
                key = text_key(text)
                self.suppressed.pop(key, None)
                self.blocks.pop(key, None)
                channel = body.get("channel") if body.get("channel") in self.cfg["channels"] else "Public"
                self._add_block(key, "text", text, "Marked as spam by you" if op == "mark_spam" else "Added by you",
                                "manual", channel=channel,
                                ttl=int(body.get("ttl_seconds") or self.cfg["block_ttl_seconds"]))
                msg = f"Blocking messages containing \"{text}\""
            elif op == "not_spam":
                self.ev({"type": "label", "label": "not_spam", "sender": body.get("sender"), "text": body.get("text"),
                         "path": body.get("path"), "packet": body.get("packet"), "caught_by": body.get("matched")})
                sender = str(body.get("sender", ""))
                if sender:
                    self.allow_senders.add(sender)
                key = body.get("matched")
                b = self.blocks.get(key) if key else None
                msg = f"'{sender}' is now trusted."
                if b and b["kind"] == "text":
                    self.blocks.pop(key)
                    self.suppressed[key] = now + 86400
                    msg += " The text rule that caught it was removed."
                elif b and b["kind"] == "hop" and self.gated(b):
                    msg += f" Their messages now get through the block on repeater {b['value']}."
                elif b and b["kind"] == "hop":
                    msg += (f" It came via blocked repeater {b['value']}; remove that block if this "
                            "repeater's traffic is genuine.")
                self.note(f"Marked a message from '{sender}' as not spam")
            elif op == "extend":
                b = self.blocks.get(body.get("key", ""))
                if not b:
                    raise ValueError("That block no longer exists")
                if body.get("permanent"):
                    b["expires"] = now + PERMANENT_SECONDS
                    msg = "Block kept permanently (until you remove it)"
                else:
                    b["expires"] = max(b["expires"], now) + int(body.get("seconds", 3600))
                if b.get("source") == "dedupe":
                    b["source"] = "manual"
                self.note(f"Extended: {self.describe(b)}")
            elif op == "rule_action":
                b = self.blocks.get(body.get("key", ""))
                if not b:
                    raise ValueError("That block no longer exists")
                act = body.get("action") or None
                if act not in (None, "drop", "log_only"):
                    raise ValueError("Unknown action")
                b["action"] = act
            elif op == "hop_mode":
                b = self.blocks.get(body.get("key", ""))
                if not b or b["kind"] != "hop":
                    raise ValueError("That block no longer exists")
                m = body.get("match") or None
                if m not in (None, "exact_paths", "contains", "contains_known"):
                    raise ValueError("Unknown matching mode")
                b["match"] = m
                self.learn_paths(list(self.events))
            elif op == "forget_path":
                b = self.blocks.get(body.get("key", ""))
                p = body.get("path", "")
                if b and (b.get("paths") or {}).pop(p, None) is not None:
                    b.setdefault("ignored_paths", []).append(p)
                    self.note(f"Repeater {b['value']}: will not block route {p}")
            elif op in ("allow_origin", "unallow_origin"):
                b = self.blocks.get(body.get("key", ""))
                hop = str(body.get("hop", "")).upper().strip()
                if not b or b["kind"] != "suffix":
                    raise ValueError("That block no longer exists")
                ua = b.setdefault("user_allowed", [])
                if op == "allow_origin" and hop not in ua:
                    ua.append(hop)
                    msg = f"Repeater {hop} is let through on this route"
                elif op == "unallow_origin" and hop in ua:
                    ua.remove(hop)
            elif op == "allow_hop":
                hop = str(body.get("hop", "")).upper().strip()
                if not HEX_HOP.fullmatch(hop):
                    raise ValueError("Enter a repeater hash of 2, 4 or 6 hex characters")
                self.allow_hops.add(hop)
                for k in [k for k, b in self.blocks.items() if b["kind"] == "hop" and hops_related(b["value"], hop)]:
                    self.blocks.pop(k)
                self.note(f"Repeater {hop} will never be blocked automatically")
            elif op == "unallow_hop":
                self.allow_hops.discard(str(body.get("hop", "")).upper())
            elif op == "allow_sender":
                self.allow_senders.add(str(body.get("sender", "")))
            elif op == "unallow_sender":
                self.allow_senders.discard(str(body.get("sender", "")))
            elif op == "allow_text":
                t = str(body.get("text", "")).strip()
                if len(t) < 3:
                    raise ValueError("Enter at least 3 characters")
                self.allow_texts.add(t)
                for k in [k for k, b in self.blocks.items() if b["kind"] == "text" and t.casefold() in b["value"].casefold()]:
                    self.blocks.pop(k)
            elif op == "unallow_text":
                self.allow_texts.discard(str(body.get("text", "")))
            elif op == "add_channel":
                name = str(body.get("name", "")).strip()
                key = str(body.get("key", "")).strip().lower()
                if name.startswith("#") and not key:
                    key = hashtag_secret(name)
                if not name or not re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}", key):
                    raise ValueError("Give a #hashtag name, or a name plus its 32-character hex key")
                self.extra_channels[name] = key
                self.rebuild_cfg()
                msg = f"SpamGuard can now read {name}"
            elif op == "remove_channel":
                self.extra_channels.pop(str(body.get("name", "")), None)
                self.rebuild_cfg()
            elif op == "clear_auto":
                for k in [k for k, b in self.blocks.items() if b.get("source") != "manual"]:
                    del self.blocks[k]
                self.note("Cleared all automatic blocks")
            elif op == "clear_suppressed":
                self.suppressed.clear()
            elif op == "reset_all":
                self.reset_all()
                msg = ("SpamGuard is starting again from scratch: every block, setting and exception has been "
                       "cleared, and it's watching for spam afresh.")
            else:
                raise ValueError("Unknown action")
            self._save_state(force=True)
            self.sync_policy(force=True)
        return {"ok": True, "message": msg}


# --------------------------------------------------------------------------- web server
def load_page() -> str:
    for p in (os.path.join(HERE, "ui.html"), "/opt/openhop_spamguard/ui.html"):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
    return "<h1>SpamGuard</h1><p>ui.html is missing - reinstall SpamGuard.</p>"


ACTIONS = {"unblock", "block_hop", "block_text", "mark_spam", "not_spam", "extend", "rule_action", "hop_mode",
           "forget_path", "allow_hop", "unallow_hop", "allow_sender", "unallow_sender", "allow_text",
           "unallow_text", "add_channel", "remove_channel", "clear_auto", "clear_suppressed",
           "allow_origin", "unallow_origin", "lockdown", "reset_all"}


class QuietServer(ThreadingHTTPServer):
    """Phones often hang up mid-response (screen locked, app switched). That's normal, so don't
    fill the log with tracebacks for it."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def make_handler(guard: SpamGuard):
    page = load_page()

    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            log.debug("http: " + fmt, *args)

        def _send(self, code, obj, ctype="application/json"):
            data = obj.encode() if isinstance(obj, str) else json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._send(200, page, "text/html; charset=utf-8")
            if path == "/status":
                return self._send(200, guard.status())
            if path == "/rules":
                return self._send(200, guard.build_rules())
            if path == "/health":
                h = guard.health()
                return self._send(503 if h["state"] == "bad" else 200,
                                  {k: h[k] for k in ("state", "problems", "warnings", "uptime", "last_check", "checks",
                                                     "openhop_ok", "rules_expected", "rules_seen", "restarts",
                                                     "watchdog")} | {"version": VERSION})
            if path == "/evidence":
                key = guard.cfg.get("listen_api_key")
                if key and self.headers.get("X-API-Key") != key:
                    return self._send(401, {"error": "This SpamGuard needs its access key"})
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query)
                days = max(1, min(60, int((q.get("days") or ["7"])[0])))
                scramble = (q.get("scramble") or ["1"])[0] != "0"
                folder = guard.cfg["evidence_dir"]
                body = (guard.evidence or EvidenceLog(folder)).export(days, scramble).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="spamguard-evidence-{time.strftime("%Y%m%d")}'
                                 f'{"-scrambled" if scramble else ""}.jsonl"')
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            key = guard.cfg.get("listen_api_key")
            if key and self.headers.get("X-API-Key") != key:
                return self._send(401, {"error": "This SpamGuard needs its access key"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                path = self.path.split("?")[0].strip("/")
                if path == "settings":
                    return self._send(200, guard.apply_settings(body))
                if path in ("check_update", "install_update"):
                    return self._send(200, guard.update_action(path, body))
                if path in ACTIONS:
                    return self._send(200, guard.action(path, body))
                return self._send(404, {"error": "not found"})
            except urllib.error.HTTPError as e:
                return self._send(502, {"error": f"Saved, but openHop returned HTTP {e.code} when applying rules"})
            except urllib.error.URLError:
                return self._send(502, {"error": "Saved, but openHop could not be reached to apply rules"})
            except Exception as e:
                return self._send(400, {"error": str(e)})

    return H


# --------------------------------------------------------------------------- config file
def load_config(path: Optional[str]) -> dict:
    cfg: dict[str, Any] = {}
    if path and os.path.exists(path):
        with open(path) as f:
            text = f.read()
        user = yaml.safe_load(text) if yaml else json.loads(text)
        if isinstance(user, dict):
            cfg.update(user)
    for old, new in LEGACY_KEYS.items():
        if old in cfg:
            cfg.setdefault(new, cfg.pop(old))
    if "action" in cfg and "mode" not in cfg:  # v4 and earlier
        cfg["mode"] = "protect" if cfg.pop("action") == "drop" else "monitor"
    cfg.pop("action", None)
    env_key = os.environ.get("OPENHOP_API_KEY")
    if env_key:
        cfg["api_key"] = env_key
    return cfg


def main():
    ap = argparse.ArgumentParser(description="openHop SpamGuard")
    ap.add_argument("--config", default="/etc/openhop_spamguard/config.yaml")
    ap.add_argument("--once", action="store_true", help="check once, print a summary, exit")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if AES is None:
        raise SystemExit("pycryptodome missing - run with openHop's venv python: "
                         "/opt/openhop_repeater/venv/bin/python spamguard.py")
    guard = SpamGuard(load_config(args.config))
    if not guard.cfg.get("api_key") or "PASTE" in str(guard.cfg.get("api_key")):
        log.error("No openHop API key set - edit %s", args.config)
    if args.once:
        guard.poll_once()
        s = guard.status()
        print(json.dumps({"mode": s["mode"], "health": s["health"], "summary": s["summary"],
                          "blocks": [b["describe"] for b in s["blocks"] if b["source"] != "dedupe"],
                          "recent": [f"{m['time']} {m['path']} {m['sender']}: {m['text'][:60]}" for m in s["recent"][:15]]},
                         indent=2, default=str))
        return
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    guard.snapshot_settings("started")
    srv = QuietServer((guard.cfg["listen_host"], int(guard.cfg["listen_port"])), make_handler(guard))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    log.info("SpamGuard %s running in %s mode - web page on port %s", VERSION, guard.cfg["mode"], guard.cfg["listen_port"])
    sd_notify("READY=1")
    try:
        guard.run(stop)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        if guard.evidence is not None:
            guard.evidence.flush(force=True, keep_days=guard.cfg["evidence_days"])
        guard._save_state(force=True)
        srv.shutdown()


if __name__ == "__main__":
    main()
