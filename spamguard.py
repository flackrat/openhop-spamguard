#!/usr/bin/env python3
# SpamGuard: channel-spam protection for openHop repeaters.
# Copyright (c) 2026 Flackrat. https://github.com/flackrat/openhop-spamguard
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU Affero General Public License as published by the Free Software Foundation, either version 3
# of the License, or (at your option) any later version. It is distributed WITHOUT ANY WARRANTY;
# see the GNU Affero General Public License (the LICENSE file) for details.
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
import base64
import collections
import statistics
import glob
import secrets
import shutil
import signal
import socket
import subprocess
import difflib
import hashlib
import hmac
import calendar
import json
import math
import logging
import os
import re
import threading
import struct
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

try:
    from Crypto.Cipher import AES  # nosec B413
except ImportError:  # pragma: no cover
    try:
        from Cryptodome.Cipher import AES  # the same library packaged as pycryptodomex (Debian, Ubuntu)
    except ImportError:
        AES = None

VERSION = "6.13.0"
# FloodGuard's own version: it ships inside SpamGuard (one plugin, one release number for installs and updates),
# but has its own history in the changelog. It only goes up when FloodGuard itself changes.
FLOODGUARD_VERSION = "1.2.5"
UPDATE_REPO = "flackrat/openhop-spamguard"  # where updates come from (owner/name on GitHub)
log = logging.getLogger("spamguard")

PAYLOAD_TYPE_GRP_TXT = 5
PAYLOAD_TYPE_ADVERT = 4
ROUTE_TRANSPORT_FLOOD, ROUTE_FLOOD = 0, 1    # MeshCore route types; 2 and 3 are direct (routed)
RULE_PREFIX = "spamguard:"
RULE_ID_BASE = 9000
PUBLIC_CHANNEL_KEY = "8b3387e9c5cdea6ac9e5edbaa115cd72"
PERMANENT_SECONDS = 10 * 365 * 86400
# SpamGuard stops how spam is sent, not what people say. Blocks on message text can't last for ever,
# a text you block by hand must be long enough to be a spam message rather than a word or a name, and it
# never stops people SpamGuard knows (they are only ever de-duplicated or slowed when they repeat).
TEXT_BLOCK_MAX_SECONDS = 7 * 86400
MANUAL_TEXT_MIN_CHARS = 12
HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- settings
# Every tunable setting, with the wording shown on the web page.
# preset=True means the Sensitivity choice (relaxed / balanced / strict) sets it.
SETTINGS_META: list[dict] = [
    # -- Repeater (first hop) blocking
    {"key": "enable_hop_rules", "risk": "Turning this off means a spammer who keeps changing names and wording can only be caught by text rules, so more spam gets through. While on, everyone whose channel messages start at a blocked repeater is blocked too, including genuine users who rely on that repeater.", "group": "Blocking by source repeater", "type": "bool",
     "label": "Block spam at its source repeater",
     "help": "When a lot of spam enters the mesh through one repeater, block channel messages that start at that repeater."},
    {"key": "hop_match_mode", "risk": "'Anything passing through, except people it knows' still blocks a genuine person on that route until SpamGuard gets to know them, and names can be copied, so it isn't watertight on its own. 'Anything passing through' also blocks known people on any route through the spam repeater, and any other repeater sharing the same short hash. 'Routes starting there' only blocks routes it has already seen, so it misses a lot of spam.", "group": "Blocking by source repeater", "type": "choice",
     "choices": [["contains_known", "Anything passing through, except people it knows (recommended)"],
                 ["exact_paths", "Routes starting there"],
                 ["contains", "Anything passing through"]],
     "label": "How to block a repeater",
     "help": "'Except people it knows' blocks every channel message passing through the spam repeater, but lets through names SpamGuard "
             "has already seen sending genuine messages (see Known people). "
             "'Routes starting there' blocks only messages that started at the spam repeater, one learnt route at a time. "
             "'Anything passing through' blocks everything through it, including people it knows."},
    {"key": "hop_random_senders", "risk": "Lower = blocks a spam repeater sooner, but a repeater used by a couple of people with code-like names (e.g. M0ABC123) could get blocked. Higher = more spam gets out before the block starts.", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 100,
     "preset": True, "label": "Random-looking names before blocking",
     "help": "Block a repeater after this many different made-up looking names (like UD6DWREK) arrive through it within the time set under How far back to count."},
    {"key": "hop_new_senders", "risk": "Lower = catches spammers using realistic names sooner, but a rally, club meet or any busy event where lots of new people talk through one repeater can trigger a block of that repeater. Higher = safer for events, slower against spam.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 200,
     "preset": True, "label": "Brand-new names before blocking",
     "help": "Block a repeater after this many names never seen before (posting once or twice) arrive through it within the time set under How far back to count. "
             "Catches spammers who use realistic names. Raise this if you host busy events."},
    {"key": "hop_campaign_senders", "risk": "Lower = quicker to block a repeater carrying a spam campaign, but a few people forwarding the same news (e.g. a road closure) through one repeater could trigger it.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 100,
     "preset": True, "label": "Spam-campaign senders before blocking",
     "help": "Block a repeater after this many different names send near-identical messages through it."},
    {"key": "hop_random_senders_long", "risk": "Lower = catches slow, drip-fed spam, but over a longer time a handful of genuine code-like names on a busy repeater can add up and trigger a block.", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 500,
     "preset": True, "label": "Slow spam: made-up names over a longer time",
     "help": "Catches a spammer who posts slowly to stay under the limits: block after this many made-up looking names within the longer time set under Timing."},
    {"key": "auto_lockdown", "group": "Blocking by source repeater", "type": "bool",
     "risk": "During a big flood, people SpamGuard doesn't know yet (newcomers) are held for 15 minutes too. Turning it off lets a flood through that comes from many repeaters at once with made-up names.",
     "label": "Short automatic lockdown during a big flood",
     "help": "When lots of made-up names flood in through many different repeaters at once, faster than blocks on single repeaters can follow, SpamGuard lets only people it knows through for 15 minutes, then stops by itself. It says so in Activity."},
    {"key": "enable_rotation_guard", "group": "Blocking by source repeater", "type": "bool",
     "risk": "While a rotation block is active, a genuine repeater that has never been heard before, sitting in the same place in the network as the spammer, is blocked until it builds up history or you allow it. Turning this off lets more spam through from a spammer who keeps changing his repeater's identity.",
     "label": "Catch a spam repeater that keeps changing its identity",
     "help": "Some firmware lets a repeater change its ID (and so its code in routes) at will. The spam then arrives from a new first repeater each time, but always through the same next repeaters. SpamGuard learns which repeaters normally appear in front of each route and, when many unknown ones start sending spam the same way, blocks unknown ones there while still letting the known ones through."},
    {"key": "rotate_first_hops", "group": "Blocking by source repeater", "type": "int", "min": 2, "max": 50,
     "preset": True, "risk": "Lower = reacts to an identity-changing spammer sooner, but a couple of new genuine repeaters appearing behind the same route at the same time as some odd-looking names could trigger it. Higher = more spam gets through first.",
     "label": "New repeaters before an identity-changing block",
     "help": "How many different never-seen-before first repeaters must deliver spam through the same route before SpamGuard treats it as one spammer changing identity. Only counts messages with strong spam signs."},
    {"key": "hop_prefer_route", "group": "Blocking by source repeater", "type": "bool",
     "risk": "Off means a surge of brand-new names through one repeater always blocks everything through that repeater (except people it knows), even when nearly all of them used one route. On means only that route is blocked, so spam arriving on the repeater's other routes is not stopped by this block.",
     "label": "Block just the route when new names nearly all use one",
     "help": "When the only sign against a repeater is brand-new names and at least 80% of them started on one route, block that route instead of everything through the repeater. Made-up names and spam campaigns still block the whole repeater."},
    {"key": "route_surge", "group": "Blocking by source repeater", "type": "bool",
     "risk": "A suggestion costs nothing until you accept it. Turning this off means a spammer who keeps changing names but always starts on the same first repeaters is only caught if you notice and block the route yourself.",
     "label": "Suggest blocking a route that suddenly carries lots of new names",
     "help": "When many brand-new names, each posting once or twice, all start on the same first two repeaters within half an hour, SpamGuard suggests blocking that route for a while. People it knows still get through. It looks at routes and names only, never what a message says."},
    {"key": "route_surge_names", "group": "Blocking by source repeater", "type": "int", "min": 3, "max": 100,
     "preset": True, "risk": "Lower = notices a surge sooner, but a busy event with lots of newcomers on one route could trigger a suggestion (or a block, if you turned on automatic route blocks). Higher = slower to notice.",
     "label": "New names on one route before suggesting a block",
     "help": "How many brand-new names must start on the same first two repeaters within half an hour before SpamGuard suggests blocking that route."},
    {"key": "route_surge_ttl", "preset": True, "group": "Blocking by source repeater", "type": "int", "min": 600, "max": PERMANENT_SECONDS, "unit": "s",
     "risk": "Longer = a spammer who pauses and returns is still held, but a genuine newcomer on that route is held longer. Shorter = mistakes clear sooner.",
     "label": "Route blocks from a suggestion last for",
     "help": "How long a route block lasts when you accept a suggestion, or when SpamGuard applies one itself. After it ends, a continuing surge is spotted again."},
    {"key": "route_auto", "group": "Blocking by source repeater", "type": "bool",
     "risk": "Off by default. When on, SpamGuard blocks a surging route without asking (at most three at a time, each for the time above), so a genuine newcomer on that route is held until the block ends or you release them. Known people always get through.",
     "label": "Block a surging route automatically",
     "help": "Instead of only suggesting, apply the route block yourself. Every one is listed under Blocks and in Activity, and can be removed in one tap. The protection level does not turn this on."},
    {"key": "route_memory_days", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 60, "unit": "days",
     "risk": "Shorter = repeaters that only talk occasionally are forgotten and may be treated as unknown during a rotation block. Longer = slightly more memory and disk use.",
     "label": "Remember normal routes for",
     "help": "How long SpamGuard remembers which repeaters normally send traffic, used to tell genuine repeaters from a spammer's changing identities."},
    # -- FloodGuard: airtime floods of any packet type (not just channel messages)
    {"key": "floodguard", "group": "FloodGuard", "type": "bool",
     "risk": "While a flood is being contained, flood packets that have already travelled more hops than the limit are not passed on by this repeater, whoever sent them, except channel messages from people SpamGuard knows. A genuine long-distance message or path search can miss this repeater for those minutes. Direct (routed) messages, replies and acknowledgements are never touched.",
     "label": "FloodGuard: contain floods when the radio gets too busy",
     "help": "Some floods aren't channel messages at all: encrypted packets with a new identity every time, sent over and over with long, padded routes. Nothing in them can be blocked by name or text. FloodGuard watches how busy this repeater's radio is instead, which a sender can't fake. When flood traffic keeps the radio busier than the limit below, it stops passing on flood packets that have already come a long way, tightening a step at a time while the flood lasts, and lifts by itself once the radio is quiet again. On by default; it spends its first three days learning this repeater's traffic and only counts meanwhile. It also holds nothing back until it has heard enough flood packets to know how far they normally come here (about 200 in a day), because on a busy mesh ordinary routes can be long."},
    {"key": "flood_busy_percent", "group": "FloodGuard", "type": "int", "min": 5, "max": 90, "unit": "%",
     "risk": "Lower = steps in sooner, but a genuinely busy evening on a big mesh could trigger it. Higher = a flood has to fill more of the airtime before anything happens.",
     "label": "Step in when the radio is busier than",
     "help": "How much of the time, over five minutes, this repeater's radio is receiving or sending packets. Ordinary traffic is usually a few percent. Only counts when most of it is flood traffic. Automatic: learnt as about twice this repeater's normal busy hour, and above the busiest genuine five minutes it has heard."},
    {"key": "flood_hop_floor", "group": "FloodGuard", "type": "int", "unit": "hops", "min": 2, "max": 32,
     "risk": "Lower = a flood is squeezed harder, but more genuine traffic from further away misses this repeater while it lasts. Higher = gentler, but a flood with short routes isn't contained.",
     "label": "Never limit flood packets to fewer hops than",
     "help": "FloodGuard starts just above the longest routes it normally hears and tightens two hops at a time while the radio stays busy, but never below this."},
    {"key": "flood_calm_minutes", "group": "FloodGuard", "type": "int", "min": 2, "max": 120, "unit": "min",
     "risk": "Shorter = genuine long-distance traffic comes back sooner, but a flood that pauses and restarts gets a few minutes through each time. Longer = steadier during on-off floods.",
     "label": "Lift once the radio has been quiet for",
     "help": "The limit is removed when the radio has been well below the busy level for this long."},
    {"key": "flood_max_unscoped", "group": "FloodGuard", "type": "int", "unit": "hops", "min": 0, "max": 64,
     "risk": "Flood packets sent without a region that have already travelled this many hops are never passed on, so senders far away who don't use a region can't reach past this repeater. 0 turns it off.",
     "label": "Most hops for flood packets with no region (0 = off)",
     "help": "Applied all the time while FloodGuard is on, busy or not. The same as MeshCore's flood.max.unscoped: packets without a region that have already had this many hops are dropped. Automatic: about twice the longest routes this repeater normally hears, between 16 and 32 (32 until it has learnt). Genuine traffic usually takes 5 to 7 hops, so a padded flood can't run to openHop's 64-hop ceiling. openHop's own Max flood hops setting also applies to flood packets, so whichever limit is lower is the one that bites."},
    {"key": "flood_max_advert", "group": "FloodGuard", "type": "int", "unit": "hops", "min": 0, "max": 64,
     "risk": "Adverts from further away than this stop reaching past this repeater, so distant nodes may not appear on maps or in contact lists beyond it. 0 turns it off.",
     "label": "Most hops for adverts (0 = off)",
     "help": "Applied all the time while FloodGuard is on. The same as MeshCore's flood.max.advert: adverts that have already had this many hops are dropped. Automatic: just past the furthest adverts this repeater normally hears, between 6 and 16 (8, MeshCore's own default, until it has learnt). openHop's own Max flood hops setting also applies to adverts, and the lower of the two is the one that counts."},
    {"key": "interference_watch", "group": "FloodGuard", "type": "bool",
     "risk": "Turned off, SpamGuard won't tell you when something nearby is drowning the channel, so a repeater that has gone half-deaf can go unnoticed for days.",
     "label": "Watch for interference on the channel",
     "help": "openHop measures the noise on the radio channel every 30 seconds. FloodGuard learns what's normal for this site and says so (here, on Health and in Activity) when the noise stays well above it, as happens with a nearby transmitter that never stops (faulty or non-compliant equipment) or deliberate jamming. Nothing can be blocked, but each episode is recorded with times and levels, which is the evidence a radio regulator asks for."},
    {"key": "interference_db", "group": "FloodGuard", "type": "int", "min": 3, "max": 40, "unit": "dB",
     "risk": "Lower = reports smaller rises, which weather, nearby electronics or a change of antenna can also cause. Higher = only strong interference is reported.",
     "label": "Report noise this far above normal",
     "help": "How much the noise on the channel has to rise above this site's normal level, for five minutes, before it counts as interference. Each 6 dB roughly halves how far away this repeater can hear."},
    # -- Privacy
    {"key": "wardrive_block", "group": "Privacy", "type": "bool",
     "risk": "This repeater stops appearing on wardriving coverage maps, which many people use to plan where repeaters are needed. Pings sent by this repeater's own companions still go out.",
     "label": "Don't repeat wardriving pings",
     "help": "Wardriving apps such as MeshMapper send a ping with the phone's GPS position on the #wardriving channel and log every repeater that echoes it, building a precise map of where each repeater can be heard. When on, this repeater still hears those pings but doesn't pass them on, so it isn't logged. Nothing else is affected: other channels, direct messages, adverts and path searches work as normal. Off by default."},
    {"key": "evidence_log", "group": "Evidence log", "type": "bool",
     "risk": "Stores channel messages (names and text) on the Pi for the days below. Public channel messages can be heard by anyone with a radio, but think before sharing the file: use 'names scrambled' when sending it to anyone.",
     "label": "Keep an evidence log",
     "help": "Records every channel message SpamGuard reads, with all its spam signals, whether it was caught, and your 'This is spam' / 'Not spam' answers. Download it to review what SpamGuard did, or to have the detection tuned against real traffic."},
    {"key": "evidence_days", "group": "Evidence log", "type": "int", "min": 1, "max": 30, "unit": "days",
     "risk": "Longer = more history for tuning, but more of people's messages kept on the Pi (about 1-3 MB per busy day).",
     "label": "Keep the evidence log for",
     "help": "Older days are deleted automatically."},
    {"key": "level_preview", "group": "Evidence log", "type": "bool",
     "risk": "Turned off, the Overview can't show what each protection level would have held. While on, the Pi spends a few minutes a day on it, at the lowest priority.",
     "label": "Work out what each protection level would have held",
     "help": "Once a day SpamGuard replays the last two days of the evidence log at eleven points along the protection level, so the Overview can show what each would have held. Nothing is changed by it. Only the Public channel and hashtag channels are replayed."},
    {"key": "max_paths_per_hop", "risk": "Higher = more routes blocked for a stubborn spammer, but more rules for openHop to check on every message. Lower = once the limit is hit, new routes from that repeater are not blocked.", "group": "Blocking by source repeater", "type": "int", "min": 1, "max": 500,
     "label": "Most routes to learn per repeater",
     "help": "Upper limit on exact routes remembered for one blocked repeater."},
    # -- Text blocking
    {"key": "enable_text_rules", "risk": "Turning this off leaves only repeater blocks and the copy and repeat checks, so spam from a new location gets through until its repeater is detected. While on, a genuine message that several people repeat can be blocked.", "group": "Blocking by message text", "type": "bool",
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
     "label": "Shortest text a block may match",
     "help": "A text rule must match at least this many characters, so it never blocks something short and common."},
    # -- Duplicate suppression
    {"key": "dedupe_enabled", "risk": "While on, anyone who sends the same long message twice (resending because nobody answered, a repeated net call, several people forwarding an alert) only has the first copy forwarded. Turning it off lets a spammer repeat himself freely under new names until other rules catch up.", "group": "Copies and repeats", "type": "bool",
     "label": "Only let the first copy of a message through",
     "help": "After any channel message is seen, the same text from anyone else is blocked for a while. "
             "Stops a spammer repeating himself under new names. Short messages are never affected."},
    {"key": "dedupe_seconds", "risk": "Longer = repeats are blocked for longer, but genuine people re-asking the same question later are blocked for longer too. Shorter = a spammer can wait it out and repeat the message.", "group": "Copies and repeats", "type": "int", "min": 30, "max": 86400, "unit": "s",
     "preset": True, "label": "Block copies for",
     "help": "How long the same text stays blocked after it is first seen."},
    {"key": "dedupe_min_chars", "risk": "Lower = more messages are treated as copies, catching shorter spam, but everyday phrases like 'Is anyone receiving me?' may only get through once per period. Higher = everyday chat is safer, short spam is not de-duplicated.", "group": "Copies and repeats", "type": "int", "min": 5, "max": 150,
     "preset": True, "label": "Only for messages at least this long",
     "help": "Messages shorter than this are never treated as copies, so 'Morning all' or 'Anyone about?' are safe."},
    {"key": "text_rule_chars", "risk": "Shorter = harder for the spammer to dodge by editing the message, but more chance of matching a genuine message that shares that wording. Longer = more precise, but small edits can dodge it.", "group": "Copies and repeats", "type": "int", "min": 5, "max": 150,
     "label": "How much of a message a copy block matches",
     "help": "How much of a message a duplicate rule matches, so small edits don't get round it."},
    {"key": "repeat_guard", "group": "Copies and repeats", "type": "bool",
     "risk": "Turned off, one name can post the same line over and over and it all goes out, because SpamGuard never blocks a person for what they say.",
     "label": "Stop one name repeating the same message",
     "help": "When the same name sends the same message again and again in a short time, further copies of that message from that name are not passed on for a while. Their first copies, and anything new they say, still go out."},
    {"key": "replay_guard", "group": "Copies and repeats", "type": "bool",
     "risk": "Turned off, a device that keeps re-sending other people's old messages (usually broken firmware) fills the channel with repeats, often dozens of copies of each. While on, someone whose device clock is badly wrong and who sends the same long message twice may have the second copy held back.",
     "label": "Stop old messages being sent again (replays)",
     "help": "Some devices pick up channel messages and send them out again later, with their own clock (often months or years wrong) and sometimes with the sender's name cut short. When a message turns up again that was first heard a while ago, either with a clock that's badly off or under a cut-short copy of the original name, further copies of it from that name are held back. The original message always went out first, and anything new from anyone is untouched."},
    {"key": "repeat_max", "group": "Copies and repeats", "type": "int", "preset": True, "min": 2, "max": 20,
     "risk": "Lower = a repeated message is cut off sooner, but someone re-sending because nobody answered may hit it. Higher = more copies go out first.",
     "label": "Copies allowed before repeats are stopped",
     "help": "How many times one name can send the same message within the time below before further copies are stopped."},
    {"key": "repeat_window_seconds", "group": "Copies and repeats", "type": "int", "min": 60, "max": 7200, "unit": "s",
     "label": "Counted over",
     "help": "The time in which those copies are counted."},
    {"key": "repeat_block_seconds", "group": "Copies and repeats", "type": "int", "preset": True, "min": 300, "max": 86400, "unit": "s",
     "risk": "Longer = a persistent repeater stays quiet for longer. Shorter = they can start again sooner.",
     "label": "Stop further copies for",
     "help": "How long further copies of that message from that name are stopped."},
    {"key": "slow_repeat", "group": "Copies and repeats", "type": "bool",
     "risk": "Turned off, one name can post the same long message again and again, spread out through the day, and all of it goes out. While on, someone who genuinely posts the same long message more than the limit below in a day has the extra copies held back for a few hours.",
     "label": "Stop slow repeating (the same message spread over hours)",
     "help": "The repeat guard above only notices copies sent within minutes of each other. This one counts the same long message from the same name over a whole day, so a message posted every hour or so is caught too. Their first few copies, and anything new they say, still go out. It only counts what is repeated, never what the message says."},
    {"key": "slow_repeat_max", "group": "Copies and repeats", "type": "int", "preset": True, "min": 2, "max": 20,
     "risk": "Lower = a repeated message is cut off sooner, but a notice that is genuinely re-posted a few times a day may be held. Higher = more copies go out first.",
     "label": "Copies allowed before slow repeats are stopped",
     "help": "How many times one name can send the same long message within the day before further copies are held."},
    {"key": "slow_repeat_window_seconds", "group": "Copies and repeats", "type": "int", "preset": True, "min": 3600, "max": 172800, "unit": "s",
     "risk": "Longer = catches slower repeating, but a message re-posted once a day for a week is never counted against the daily limit anyway. Shorter = only quick repeating counts.",
     "label": "Counted over (slow repeats)",
     "help": "The time in which those copies are counted."},
    {"key": "slow_repeat_hold_seconds", "group": "Copies and repeats", "type": "int", "preset": True, "min": 900, "max": 86400, "unit": "s",
     "risk": "Longer = a persistent repeater stays quiet for longer. Shorter = a copy gets through sooner.",
     "label": "Hold further copies for (slow repeats)",
     "help": "How long further copies of that message from that name are held. While they keep repeating it, one copy gets through each time this period ends."},
    # -- Known people
    {"key": "known_min_msgs", "group": "Known people", "type": "int", "min": 1, "max": 20,
     "risk": "1 = names become known very quickly, which is easier to abuse. Higher = harder to fake, but genuine newcomers wait longer before they get through repeater blocks and lockdowns.",
     "label": "Genuine messages before a name counts as known",
     "help": "A name counts as known after this many genuine messages. Trusted names always count."},
    {"key": "known_days", "group": "Known people", "type": "int", "min": 1, "max": 365, "unit": "days",
     "risk": "Shorter = occasional users are forgotten and treated as unknown again. Longer = a longer list kept on the Pi and in openHop.",
     "label": "Remember known names for",
     "help": "A name is forgotten if it hasn't sent anything for this long."},
    {"key": "hold_links", "group": "Known people", "type": "choice",
     "choices": [["campaign", "While a spam campaign is under way (recommended)"], ["always", "Always"], ["off", "Never"]],
     "risk": "While on, a genuine first-time poster sharing a link is held too. 'Always' does this all the time; 'while a campaign is under way' only for an hour after spam campaign activity.",
     "label": "Hold links from names it doesn't know",
     "help": "Spammers often post links. When on, channel messages containing a link are blocked unless the sender is a known name."},
    # -- Names
    {"key": "name_score_threshold", "risk": "Lower (1-2) = catches more made-up names, but more genuine names, such as callsigns with numbers or node names, may count as random and push their repeater towards a block. Higher = fewer false alarms, more spam names missed.", "group": "Sender names", "type": "int", "min": 1, "max": 6,
     "preset": True, "label": "How random a name must look",
     "help": "Names are scored 0-6 for looking machine-generated. "
             "Names at or above this score count as random. Lower = stricter."},
    {"key": "random_name_patterns", "risk": "A pattern that is too broad (e.g. any 8 letters) marks genuine people as random. Try new patterns in Monitor mode first.", "group": "Sender names", "type": "list",
     "label": "Extra name patterns (for experts)",
     "help": "Optional, for experts. One pattern (a regular expression) per line. Names matching any of these always count as random. Matching ignores case."},
    {"key": "detect_garbage", "risk": "Turning this off lets junk-text floods through until other signs catch up. While on, a newcomer whose message is genuinely garbled could be counted as spam.", "group": "Sender names", "type": "bool",
     "label": "Treat unreadable random text as spam",
     "help": "Some floods send meaningless junk text under made-up names. When on, junk messages like that count as spam. "
             "Ordinary messages in any language, with emoji or kaomoji, are not affected."},
    # -- Timing
    {"key": "window_seconds", "risk": "Longer = slow spam is easier to spot, but on a busy repeater genuine new users add up and can trip the 'brand-new names' limit. Shorter = only fast bursts are detected.", "group": "Timing", "type": "int", "min": 60, "max": 86400, "unit": "s",
     "label": "How far back to count",
     "help": "How far back SpamGuard looks when counting senders through a repeater."},
    {"key": "long_window_seconds", "risk": "Longer = catches very slow spam, but random-looking genuine names accumulate over the window and can add up to a block on busy repeaters.", "group": "Timing", "type": "int", "min": 600, "max": 86400, "unit": "s",
     "label": "How far back to count slow spam",
     "help": "A longer look-back used to catch spam sent slowly."},
    {"key": "block_ttl_seconds", "preset": True, "risk": "Longer = a spammer who pauses and returns is still blocked, but genuine users behind a wrongly blocked repeater stay blocked longer. Shorter = mistakes clear faster, but spam may return between blocks.", "group": "Timing", "type": "int", "min": 300, "max": PERMANENT_SECONDS, "unit": "s",
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
    {"key": "map_directory", "group": "Spam sources map", "type": "bool",
     "risk": "Once a day the Pi downloads the public MeshCore map's repeater list from map.meshcore.dev (a few MB, nothing is sent). Turned off, the map only knows repeaters whose adverts your openHop has heard, so spam entering far away is placed less precisely.",
     "label": "Use the public MeshCore map for repeater locations",
     "help": "Adds the locations of repeaters too far away for your openHop to hear their adverts, so spam routes can be traced back closer to where they started."},
    {"key": "openhop_autofix", "group": "Updates", "type": "bool",
     "risk": "When on, SpamGuard edits one line of openHop (with a backup) and restarts openHop for a few seconds whenever an openHop update removes the fix. Turned off, blocked spam can sometimes be let through until you apply the fix by hand.",
     "label": "Keep openHop's rule-check fix in place",
     "help": "openHop has a bug that can sometimes let blocked spam through. SpamGuard applies a one-line fix when it updates, and puts it back if an openHop update removes it, until openHop releases its own fix."},
    {"key": "auto_protect", "group": "Timing", "type": "bool",
     "risk": "Turned off, SpamGuard stays in Monitor until you switch it to Protect yourself, so nothing is blocked if you never come back to the page.",
     "label": "Switch to Protect by itself after watching",
     "help": "A new SpamGuard starts in Monitor. Once it has watched for at least a day and seen enough spam, with nothing it would block marked as genuine and few genuine-looking messages held, it switches itself to Protect and says so in Activity. Choosing Monitor yourself turns this off."},
    {"key": "poll_seconds", "risk": "Lower = blocks land faster, but the Pi does a little more work. Higher = more spam copies slip through before a rule exists.", "group": "Timing", "type": "int", "min": 1, "max": 300, "unit": "s",
     "label": "Check for new packets every",
     "help": "Lower is faster to react. 3 seconds is a good balance."},
    {"key": "live_feed", "risk": "Turned off, SpamGuard only looks for new packets on the timer above, so it reacts a second or two later.", "group": "Timing", "type": "bool",
     "label": "React as soon as openHop hears a packet",
     "help": "Listens to openHop's live packet feed and checks straight away when something arrives, instead of waiting for the next timed check. The timed check carries on as a backup."},
    {"key": "rules_after_yours", "risk": "On = your own openHop rules are checked first, so a broad 'allow' rule of yours (for example letting everything from one repeater through) also lets spam through before SpamGuard's blocks are reached. Off = SpamGuard's text and campaign blocks are checked first. Route blocks, links, lockdown and blocks set to let known people through are checked after your own rules, so one of your allow rules can let them through. Your own rules are never changed either way.", "group": "Timing", "type": "bool",
     "label": "Put SpamGuard's rules after your own openHop rules",
     "help": "Changes only the order in openHop's policy list. Off by default."},
    {"key": "max_total_rules", "risk": "Higher = nothing is dropped during a very heavy attack, but every rule is checked against every channel message, which costs CPU on small Pis. Lower = the oldest duplicate rules are dropped first.", "group": "Timing", "type": "int", "min": 20, "max": 500,
     "label": "Most rules at once",
     "help": "Safety limit on rules written to openHop. The oldest duplicate rules are dropped first."},
]
META_BY_KEY = {m["key"]: m for m in SETTINGS_META}

PRESETS: dict[str, dict] = {
    "relaxed": {"rotate_first_hops": 4, "hop_random_senders": 5, "hop_new_senders": 10, "hop_campaign_senders": 5,
                "hop_random_senders_long": 8, "text_distinct_senders": 4, "similarity": 80,
                "dedupe_seconds": 600, "dedupe_min_chars": 40, "name_score_threshold": 4,
                "repeat_max": 4, "slow_repeat_max": 4, "slow_repeat_hold_seconds": 7200,
                "repeat_block_seconds": 1800, "slow_repeat_window_seconds": 43200, "block_ttl_seconds": 10800,
                "route_surge_names": 12, "route_surge_ttl": 3600},
    "balanced": {"rotate_first_hops": 3, "hop_random_senders": 3, "hop_new_senders": 6, "hop_campaign_senders": 3,
                 "hop_random_senders_long": 5, "text_distinct_senders": 3, "similarity": 65,
                 "dedupe_seconds": 900, "dedupe_min_chars": 30, "name_score_threshold": 3,
                 "repeat_max": 3, "slow_repeat_max": 3, "slow_repeat_hold_seconds": 10800,
                 "repeat_block_seconds": 3600, "slow_repeat_window_seconds": 86400, "block_ttl_seconds": 21600,
                 "route_surge_names": 8, "route_surge_ttl": 7200},
    "strict": {"rotate_first_hops": 2, "hop_random_senders": 2, "hop_new_senders": 4, "hop_campaign_senders": 2,
               "hop_random_senders_long": 3, "text_distinct_senders": 2, "similarity": 55,
               "dedupe_seconds": 1800, "dedupe_min_chars": 24, "name_score_threshold": 2,
               "repeat_max": 2, "slow_repeat_max": 2, "slow_repeat_hold_seconds": 21600,
               "repeat_block_seconds": 7200, "slow_repeat_window_seconds": 129600, "block_ttl_seconds": 43200,
               "route_surge_names": 5, "route_surge_ttl": 14400},
}
# The protection level (0-100) slides smoothly between the three presets: 0 is relaxed, 50 balanced and
# 100 strict, and every value in between is worked out from the two either side. Tougher also means longer.
SENSITIVITY_LEVEL = {"relaxed": 0, "balanced": 50, "strict": 100}
LEVEL_NAMES = ((20, "Gentle"), (40, "Easy-going"), (60, "Balanced"), (80, "Firm"), (101, "Tough"))
PREVIEW_LEVELS = tuple(range(0, 101, 10))


def level_values(level) -> dict:
    """The settings a protection level sets. Rounded half up, the same way the web page does it."""
    level = max(0, min(100, int(level)))
    lo, hi, f = ((PRESETS["relaxed"], PRESETS["balanced"], level / 50) if level <= 50
                 else (PRESETS["balanced"], PRESETS["strict"], (level - 50) / 50))
    return {k: int(lo[k] + (hi[k] - lo[k]) * f + 0.5) for k in PRESETS["balanced"]}


def level_name(level) -> str:
    return next(n for top, n in LEVEL_NAMES if int(level) < top)


def suggest_level(rep: dict) -> Optional[int]:
    """The level that would have held the most spam for the fewest messages worth a look, and never one
    you marked as fine (each counts three times against it). The gentlest such level wins a tie. No
    suggestion from too little traffic, or when nothing like spam was seen."""
    levels = rep.get("levels") or []
    span = (rep.get("to") or 0) - (rep.get("from") or 0)
    if not levels or (rep.get("messages") or 0) < SpamGuard.PREVIEW_MIN_MESSAGES or span < 12 * 3600:
        return None
    if not any(lv["spam"] + lv["repeats"] for lv in levels):
        return None
    best = max(levels, key=lambda lv: (lv["spam"] + lv["repeats"] - lv["check"] - 3 * lv["wrong"], -lv["level"]))
    return best["level"]


def level_sensitivity(level) -> str:
    """The nearest of the three old presets, for anything that still reads 'sensitivity'."""
    return min(SENSITIVITY_LEVEL, key=lambda s: abs(SENSITIVITY_LEVEL[s] - int(level)))


DEFAULT_CONFIG: dict[str, Any] = {
    "openhop_url": "http://127.0.0.1:8000",
    "api_key": "",
    "mode": "monitor",                    # monitor | protect
    "paused": False,
    "sensitivity": "balanced",            # relaxed | balanced | strict (the older choice: 0, 50 or 100 below)
    "level": 50,                          # protection level 0-100: how firmly SpamGuard pushes back
    "channels": {"Public": PUBLIC_CHANNEL_KEY},
    "hashtag_channels": [],               # e.g. ["#test", "#chat"] - keys are worked out from the name
    "enable_hop_rules": True,
    "hop_match_mode": "contains_known",
    "known_min_msgs": 3,
    "known_days": 30,
    "hold_links": "campaign",
    "max_paths_per_hop": 50,
    "enable_rotation_guard": True,
    "auto_lockdown": True,
    "floodguard": True,                   # on, but only counts until it has learnt this mesh (FG_LEARN_DAYS)
    "flood_busy_percent": 15,
    "flood_hop_floor": 8,
    "flood_calm_minutes": 10,
    "flood_max_unscoped": 32,             # recommended; a value you saved yourself (including 0) is kept
    "flood_max_advert": 8,
    "route_memory_days": 7,
    "route_surge": True,                  # suggest blocking a route that suddenly carries lots of new names
    "hop_prefer_route": True,             # block just the route when brand-new names nearly all started on one
    "route_auto": False,                  # ...and only apply it without asking if you turn this on
    "interference_watch": True,
    "interference_db": 10,
    "wardrive_block": False,
    "evidence_log": False,
    "evidence_days": 7,
    "level_preview": True,
    "evidence_dir": "/var/lib/openhop_spamguard/evidence",
    "max_origins_per_route": 60,
    "enable_text_rules": True,
    "min_rule_chars": 14,
    "dedupe_enabled": True,
    "repeat_guard": True,
    "replay_guard": True,
    "repeat_max": 3,
    "repeat_window_seconds": 600,
    "repeat_block_seconds": 3600,
    "slow_repeat": True,
    "slow_repeat_max": 3,
    "slow_repeat_window_seconds": 86400,
    "slow_repeat_hold_seconds": 10800,
    "text_rule_chars": 40,
    "random_name_patterns": [r"(?=.*\d)(?=.*[a-z])[a-z0-9]{8}"],
    "detect_garbage": True,
    "window_seconds": 600,
    "long_window_seconds": 7200,
    "block_ttl_seconds": 6 * 3600,
    "spam_text_days": 7,
    "hop_block_ttl_seconds": 2 * 3600,
    "update_check": "daily",
    "map_directory": False,
    "openhop_autofix": True,
    "update_repo": UPDATE_REPO,
    "poll_seconds": 3,
    "auto_protect": True,
    "live_feed": True,
    "fetch_limit": 500,
    "max_total_rules": 300,
    "rules_after_yours": False,
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
# FloodGuard settings it learns from this repeater's own traffic, and the range a learnt value stays in.
FG_AUTO_KEYS = {"flood_busy_percent": (10, 40), "flood_max_unscoped": (16, 32), "flood_max_advert": (6, 16)}
FG_LEARN_DAYS = 3
# Settings the page may change, besides those in SETTINGS_META.
EXTRA_TUNABLES = {"mode", "paused", "sensitivity", "level"}
# Housekeeping choices, not detection: both resets leave these as you set them.
KEEP_ON_RESET = {"evidence_log", "evidence_days", "level_preview", "update_check", "map_directory", "openhop_autofix",
                 "wardrive_block"}
# A settings profile holds detection settings only: never channels, keys, exceptions, the mode, the evidence
# log, updates or how SpamGuard runs on this machine.
PROFILE_FORMAT = "spamguard-profile"
PROFILE_EXCLUDE = KEEP_ON_RESET | {"auto_protect", "poll_seconds", "live_feed", "rules_after_yours", "floodguard"}
MAX_PROFILES = 50


def profile_keys() -> list[str]:
    return [m["key"] for m in SETTINGS_META if m["key"] not in PROFILE_EXCLUDE]
# openHop release that includes its own rule-check fix (openhop_repeater #520/#521); None until released.
OPENHOP_FIXED_IN: Optional[str] = None
PUBLIC_MAP_URL = "https://map.meshcore.io/api/v1/nodes"
# Running from the Docker image: settings can come from environment variables, data lives in /data,
# and updates come from pulling a new image rather than the Update button.
IN_DOCKER = os.environ.get("SPAMGUARD_DOCKER") == "1"
DOCKER_UPDATE = "docker compose pull && docker compose up -d"
# Running as an openHop plugin: openHop installs, starts and updates it from System > Plugins.
IN_PLUGIN = os.environ.get("SPAMGUARD_PLUGIN") == "1"


# Only one SpamGuard may manage a repeater's rules. The one in charge keeps a marker in openHop's policy
# (objects.spamguard_owner) and refreshes it every few minutes; any other copy waits in standby until the
# marker is released to it or goes stale (the other copy stopped).
OWNER_KEY = "spamguard_owner"
LEASE_SECONDS = 900
LEASE_REFRESH = 600
PLUGIN_ID = "openhop-spamguard"
KIND_NAMES = {"normal": "a normal install", "docker": "a Docker container", "plugin": "the openHop plugin"}


def install_kind() -> str:
    return "plugin" if IN_PLUGIN else "docker" if IN_DOCKER else "normal"


TUNE_URL = "https://raw.githubusercontent.com/flackrat/openhop-spamguard/main/tune-openhop.sh"


def openhop_in_container() -> bool:
    """openHop itself runs in a container (and SpamGuard, as its plugin, inside it)."""
    return IN_PLUGIN and os.path.exists("/.dockerenv")


def fix_hint(which: str) -> Optional[str]:
    """How to apply one of SpamGuard's openHop fixes on this kind of install, or None if it can't be."""
    flag = " --rulefix" if which == "rule" else ""
    if install_kind() == "normal":
        return ("press Apply openHop fix on the Health page, or run sudo bash /opt/openhop_spamguard/tune-openhop.sh"
                + flag) if which == "rule" else "sudo bash /opt/openhop_spamguard/tune-openhop.sh"
    if IN_PLUGIN and not openhop_in_container():
        return f"run this on the Pi (or whatever computer runs openHop): curl -fsSL {TUNE_URL} -o tune-openhop.sh && sudo bash tune-openhop.sh{flag}"
    return None


def fix_command(which: str) -> Optional[str]:
    """Just the command to copy for a plugin running next to openHop on the same computer, else None."""
    if IN_PLUGIN and not openhop_in_container():
        flag = " --rulefix" if which == "rule" else ""
        return f"curl -fsSL {TUNE_URL} -o tune-openhop.sh && sudo bash tune-openhop.sh{flag}"
    return None


def hidden_settings() -> set:
    """Settings that mean nothing for this kind of install, so the page doesn't offer them."""
    return set() if install_kind() == "normal" else {"openhop_autofix"}


def plugin_version(v: str = VERSION) -> str:
    """SpamGuard's version as openHop plugin manifests write it (5.21 -> 5.21.0)."""
    return ".".join((v.split(".") + ["0", "0"])[:3])


def managed_update() -> Optional[str]:
    """How to update when SpamGuard can't update itself (Docker or openHop plugin), else None."""
    if IN_DOCKER:
        return f"SpamGuard runs in Docker here. To update, run {DOCKER_UPDATE} in the folder with your compose file."
    return None
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


_PAYLOAD_NAMES = {4: "an advert", 5: "a channel message"}


def plain_rule(rule: dict) -> str:
    """One of SpamGuard's openHop rules in plain English, for the page. Never shows a channel key."""
    then = (rule.get("then") or {}).get("action")
    lead = {"drop": "Blocks", "log_only": "Only watches (nothing is blocked)", "allow": "Lets through"}.get(then, "Applies to")

    def show(v) -> str:
        t = re.sub(r"\s+", " ", str(v)).strip()
        return '"' + (t[:80] + "..." if len(t) > 80 else t) + '"'

    def one(c: dict) -> str:
        f, op, v = c.get("field"), c.get("op"), c.get("value")
        if f == "payload_type" and op == "equals":
            return "is " + _PAYLOAD_NAMES.get(v, f"packet type {v}")
        if f == "payload_type" and op == "in":
            return "is " + " or ".join(_PAYLOAD_NAMES.get(x, f"packet type {x}") for x in (v or []))
        if f == "channel_hash":
            return "is on a channel SpamGuard reads"
        if f == "channel_decryptable":
            return "can be read by this repeater"
        if f == "channel_message_body" and op == "contains":
            return f"contains the text {show(v)}"
        if f == "channel_sender" and op == "equals":
            return f"is from {show(v)}"
        if f == "channel_sender" and op == "not_equals":
            return f"is not from {show(v)}"
        if f == "channel_sender" and op == "in":
            return "is from someone SpamGuard knows"
        if f == "path_hashes" and op in ("contains", "intersects"):
            return f"came through repeater {v if not isinstance(v, list) else ' or '.join(map(str, v))}"
        if f == "route_type" and op == "equals":
            return "was sent as a flood" if v in (0, 1) else "was sent along a direct route"
        if f == "route_type" and op == "in":
            return "was sent as a flood" if set(v or []) <= {0, 1} else "has one of several route types"
        if f == "hop_count" and op in ("gte", "greater_than", "gt"):
            return f"has come {v} or more hops" if op == "gte" else f"has come more than {v} hops"
        if f == "hop_count" and op == "equals":
            return f"has come exactly {v} hops"
        if f == "local_transmission" and op == "not_equals":
            return "was not sent by this repeater itself"
        return f"{f} {op} {show(v)}"

    def walk(cond) -> list:
        if not isinstance(cond, dict):
            return []
        if "all" in cond:
            return [x for c in cond["all"] for x in walk(c)]
        if "any" in cond:
            parts = [" and ".join(walk(c)) for c in cond["any"]]
            return ["(" + " or ".join(p for p in parts if p) + ")"]
        return [one(cond)]

    conds = walk(rule.get("if"))
    return lead + (" a packet that " + ", ".join(conds) if conds else " every packet")


def oh_sender(name) -> str:
    """The sender as openHop's rules see it: a message without a "Name: " prefix is from "Unknown" there
    (SpamGuard keeps such a sender blank), so a rule about it must say "Unknown" to match anything."""
    return str(name or "").strip() or "Unknown"


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
            # AES in ECB mode is what MeshCore itself uses for channel messages; SpamGuard only reads them,
            # and never uses it to protect anything of its own.
            pt = AES.new(key[:16], AES.MODE_ECB).decrypt(padded)[: len(ct)]
            # [timestamp 4][flags 1]["sender: text"][zero padding]
            msg = pt[5:].split(b"\x00", 1)[0].decode("utf-8", "replace")
            sender, text = (msg.split(": ", 1) if ": " in msg else ("", msg))
            return {"channel": name, "sender": sender.strip(), "text": text, "sent": int.from_bytes(pt[:4], "little")}
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


_SCRIPTS = ((0x0250, 0x02AF, "ipa"), (0x0370, 0x03FF, "greek"), (0x0400, 0x052F, "cyrillic"),
            (0x0530, 0x058F, "armenian"), (0x0590, 0x05FF, "hebrew"), (0x0600, 0x06FF, "arabic"),
            (0x0750, 0x077F, "arabic"), (0x0900, 0x0DFF, "indic"), (0x0E00, 0x0E7F, "thai"),
            (0x10A0, 0x10FF, "georgian"), (0x1100, 0x11FF, "hangul"), (0x1E00, 0x1EFF, "latin"),
            (0x1F00, 0x1FFF, "greek"), (0x3040, 0x30FF, "cjk"), (0x3100, 0x9FFF, "cjk"),
            (0xAC00, 0xD7AF, "hangul"), (0xF900, 0xFAFF, "cjk"), (0xFB50, 0xFEFF, "arabic"),
            (0xFF00, 0xFFEF, "cjk"))
def _script(c):
    """Which writing system a character belongs to, or 'symbol', 'mark' or 'bad' (unreadable bytes,
    control or unassigned characters). None for spaces, digits, ordinary punctuation and emoji."""
    o = ord(c)
    if o < 0x80:
        return "latin" if c.isalpha() else None
    if c == "\ufffd":
        return "bad"
    if EMOJI_BASE.match(c) or EMOJI_PARTS.match(c):
        return None
    cat = unicodedata.category(c)
    if cat in ("Cc", "Cf", "Co", "Cn", "Cs"):
        return "bad"
    if cat in ("Mn", "Me", "Mc"):
        return "mark"
    if cat[0] != "L":
        return "symbol" if cat in ("So", "Sm", "Sk") else None
    if o < 0x250:
        return "latin"
    for lo, hi, name in _SCRIPTS:
        if lo <= o <= hi:
            return name
    return "other"

def garbage_score(text: str) -> int:
    """0 and up: how much a message looks like random bytes rather than words. Floods of made-up names
    sending unreadable text mix several writing systems letter by letter, with symbols and broken bytes;
    real messages, in any language and with any emoji, kaomoji or fancy lettering, do not."""
    # Characters from Unicode planes 4-13, where nothing is assigned yet: no phone or app can type
    # these, so even a very short message containing one is random bytes.
    if any(0x40000 <= ord(c) < 0xE0000 for c in text):
        return 9
    chars = [c for c in text if not c.isspace()]
    if len(chars) < 3:
        return 0
    if len(chars) < 6:
        # Short ones: a few characters from different writing systems and symbol sets, with no plain
        # letters or digits at all ("ĔІブ", "Ï┤╫☙ɛ", "ᵐᦐ৺"). Real short messages ("ok", "73", "👍",
        # "日本語", "♥♥") don't mix like that.
        if any(c.isascii() and c.isalnum() for c in chars):
            return 0
        tags = {_script(c) for c in chars} - {None}
        odd = sum(1 for c in chars if _script(c) in ("symbol", "bad") or (c.isdigit() and not c.isascii()))
        letters = tags - {"symbol", "mark", "bad"}
        if (len(tags) >= 2 and odd) or len(letters) >= 3:
            return 3
        return 0
    tags = [_script(c) for c in chars]
    bad, odd = tags.count("bad"), tags.count("symbol") + tags.count("mark")
    letters = {t for t in tags if t not in (None, "bad", "symbol", "mark")}
    # neighbouring letters from different writing systems ("πЖĽЂ"): real words, in any language, don't do this
    lt = [_script(c) for c in text]
    switches = sum(1 for x, y in zip(lt, lt[1:]) if x != y and x in letters and y in letters)
    s = 0
    if bad >= 2 and bad / len(chars) >= 0.08:
        s += 2
    if bad >= 3:   # three or more broken characters: genuine apps send valid text
        s += 1
    if bad >= 5:
        s += 1
    if len(letters) >= 3:
        s += 1
    if len(letters) >= 4 and switches:
        s += 1
    if switches >= 2:
        s += 1
    if switches >= 4:
        s += 1
    if switches and odd / len(chars) >= 0.15:
        s += 1
    return s
def is_garbage(text: str) -> bool:
    return garbage_score(text) >= 3


MENTION = re.compile(r"@\[[^\]\n]{1,48}\]")  # "@[Sam-N0CALL]": who a reply is to, not what it says


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
    if re.search(f"[A-Za-z0-9][{hidden}]+[A-Za-z0-9]", text) or re.search("[\u200b\u2060\ufeff\u00ad\u180e]", text):
        return True
    # An emoji wedged between letters of one word: "Bu🔥ilt". Not for display names, where a
    # symbol inside the name is just styling ("HDZ✝rt").
    if not name and re.search("[A-Za-z]" + EMOJI_ANY.pattern + "+[A-Za-z]", text):
        return True
    for word in re.findall(r"\w+", text):
        if LATIN.search(word) and NON_LATIN_LETTER.search(word):
            return True
    return False


CALLSIGN = re.compile(r"(?:[A-Z]{1,2}|[A-Z]\d|\d[A-Z])\d{1,2}[A-Z]{1,4}\d?", re.I)


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
    # A real-looking first name with a random tag stuck on ("Arno-q7k2d", "Henk203_k81zt",
    # "Wim.rig.c9d1"): a generator making names look human. The tag mixes letters and digits.
    m = re.fullmatch(r"[A-Z][a-z]{2,11}\d{0,4}[-_.](?:[a-z]{2,8}[-_.])?([a-z0-9]{4,6})", plain)
    if m:
        tag = m.group(1)
        if re.search(r"\d", tag) and re.search(r"[a-z]", tag):
            flips = sum(1 for a, b in zip(tag, tag[1:]) if a.isdigit() != b.isdigit())
            return min(6, score + 2 + (1 if flips >= 2 else 0))
    # Only judge single-word, letters-and-digits names; "Dave M", "BOT-01-X", "Ohm🔌" are left alone.
    if not re.fullmatch(r"[A-Za-z0-9]{6,16}", plain):
        return min(score, 6)
    # "Dave1985", "Bob42", "Sarah2": a word followed by a number reads as a person.
    if re.fullmatch(r"[A-Z]?[a-z]{2,}\d{1,4}", plain):
        return 1
    # A radio callsign on its own (such as "N0CALL"), sometimes with a
    # station number ("N5LVC1"), is a person, not a made-up name.
    if len(plain) <= 7 and CALLSIGN.fullmatch(plain) and (plain.isupper() or plain.islower()):
        return 1
    # A device's default name is the start of its own key ("198EC9D5"): a person who hasn't
    # renamed their node. Counted less than a made-up name, but not ignored.
    if re.fullmatch(r"[0-9A-F]{8}|[0-9a-f]{8}", plain) and re.search(r"\d", plain) and re.search(r"[A-Fa-f]", plain):
        score_cap = 2
    elif score == 0 and plain.isalpha() and plain.isupper():
        # Capital letters only, no digits ("HLDWNTR", "PRKSTVN"): how people abbreviate a node or a
        # club name. Few vowels and a run of consonants are normal there, so it counts a little, not as
        # made-up. Generated names mix in digits or lower case, which still score fully.
        score_cap = 2
    else:
        score_cap = 6
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
    return min(score, score_cap)


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
    return "text:" + hashlib.sha1(snippet.encode(), usedforsecurity=False).hexdigest()[:10]


def hops_related(a: str, b: str) -> bool:
    """Same repeater at different hash widths: '27' relates to '27AB' and '27AB01'."""
    return a.startswith(b) or b.startswith(a)


HEX_HOP = re.compile(r"[0-9A-F]{2}|[0-9A-F]{4}|[0-9A-F]{6}")
# Blocks that hold people back by where their message came from, rather than by what it says.
ROUTE_SURGE_SECONDS = 1800   # how far back a route surge is counted
ROUTE_AUTO_MAX = 3           # most automatic route blocks at once
PEOPLE_KINDS = ("hop", "suffix", "links", "lockdown", "route")
ROUTE_MAX_HOPS = 4


def parse_route(text: str) -> list[str]:
    """'BA>AA', 'ba aa' or '0xBA,0xAA' -> ['BA', 'AA']: the first repeaters a message passed through, in order."""
    hops = [h[2:] if h.startswith("0X") else h for h in re.split(r"[\s>,]+", str(text or "").upper().strip()) if h]
    if not 2 <= len(hops) <= ROUTE_MAX_HOPS:
        raise ValueError(f"Enter the first 2 to {ROUTE_MAX_HOPS} repeaters of the route, e.g. 27>B1")
    if not all(HEX_HOP.fullmatch(h) for h in hops):
        raise ValueError("Each repeater is a code of 2, 4 or 6 hex characters, e.g. 27>B1")
    if len({len(h) for h in hops}) != 1:
        raise ValueError("Use codes of the same length for every repeater, as shown in the route")
    return hops


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
        m = {ln.split(":")[0]: int(ln.split()[1]) for ln in mem.splitlines() if ln.split()[1:2] and ln.split()[1].isdigit()}
        if "MemTotal" in m and "MemAvailable" in m:
            out["mem_avail_pct"] = round(100 * m["MemAvailable"] / m["MemTotal"])
    st = _read("/proc/self/status")
    if st:
        for ln in st.splitlines():
            if ln.startswith("VmRSS:"):
                out["rss_mb"] = round(int(ln.split()[1]) / 1024)
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
                    lines.extend(ln for ln in f.read().splitlines() if ln.strip())
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
    __slots__ = ("ts", "path", "first_hop", "sender", "text", "channel", "norm", "shingles", "garbage",
                 "name_score", "random", "obfuscated", "matched", "campaign", "exempt", "recorded", "logged", "packet", "seen_at",
                 "length", "leaked", "known_then", "in_passing", "local", "sent_ts", "replay")

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
        self.garbage = is_garbage(MENTION.sub(" ", text))   # unreadable random text
        self.matched: Optional[str] = None
        self.known_then: Optional[bool] = None   # was the sender known when the message arrived?
        self.in_passing = False                   # held only for passing THROUGH a blocked repeater
        self.campaign: Optional[int] = None
        self.exempt = False
        self.local = False   # sent by this repeater itself (one of its own companions)
        self.sent_ts = 0     # the time the sender's device put in the message (its own clock)
        self.replay = False  # an old message sent again by another device
        self.recorded = False
        self.logged = False
        self.packet = ""
        self.seen_at = ts
        self.length = 0
        self.leaked = False


# --------------------------------------------------------------------------- core
class SpamGuard:
    def __init__(self, cfg_file: dict):
        self.file_cfg = cfg_file
        self.lock = threading.RLock()
        self.level_preview: Optional[dict] = None
        self._preview_busy = False
        self._preview_tried = time.time() - self.PREVIEW_EVERY + 600   # first check 10 minutes after starting
        self.events: collections.deque[Event] = collections.deque()
        self.seen_packets: collections.OrderedDict[str, float] = collections.OrderedDict()
        # Packets already written to the evidence log. Kept across restarts, because on start-up
        # openHop's recent packets are read again to rebuild the picture.
        self.logged_packets: collections.OrderedDict[str, None] = collections.OrderedDict()
        self.counted_packets: collections.OrderedDict[str, None] = collections.OrderedDict()  # already counted
        self.last_packet_ts: Optional[float] = None    # newest packet of any kind openHop reported
        self.heard_at: Optional[float] = None          # when that last moved forward
        # openHop's transmit failures (packet times) and its newest successful transmit, to spot a dead radio
        self.tx_fails: collections.deque[float] = collections.deque(maxlen=50)
        self.tx_ok_at: Optional[float] = None
        self.tx_oks: collections.deque[float] = collections.deque(maxlen=200)
        self._power: tuple[float, Optional[dict]] = (0.0, None)   # (when checked, result of vcgencmd)
        # Bytes per hop openHop is sending (its path.hash.mode: 1, 2 or 3), from the newest routed packets
        self.hash_size = 1
        self.hops_stale = 0          # route blocks not written this time because they were learnt at another size
        # A mesh can mix hop sizes (each sender picks its own), so every size seen lately is remembered.
        self.hop_sizes: dict[int, float] = {}
        # Repeaters and room servers heard in adverts (full key -> when), to spot hop bytes they share
        self.node_ids: collections.OrderedDict[str, float] = collections.OrderedDict()
        self.hops_narrowed = 0       # route blocks whose shorter form was left out: another repeater shares it
        self.hops_shared = 0         # 1-byte route blocks on a byte more than one known repeater uses
        self._route_sig = None
        # How far behind real time openHop's packet list is: (when measured, seconds behind)
        self.lag_samples: collections.deque[tuple] = collections.deque(maxlen=200)
        self.use_filtered: Optional[bool] = None   # openHop's /api/filtered_packets available?
        self.update_info: dict = {"latest": None, "notes": "", "url": "", "checked": None, "error": None}
        self._update_checking = False
        self.sender_history: dict[str, dict] = {}  # name -> {first, count, hops:set}
        # Slow repeating: "name|channel|hash of the message" -> {"who", "ch", "snip", "ts": [times of each separate send]}
        self.slow_sends: dict[str, dict] = {}
        # Names that carried on another name's all-day repeat count: name -> {"after": [earlier names], "ts": when}
        self.name_links: dict[str, dict] = {}
        # Per name, per day (local midnight): [messages heard, copies held], for "Most held, last 7 days"
        self.held_names: dict[str, dict] = {}
        # Where repeat spammers are heard from: name -> first hops of the route -> day -> messages. Only kept
        # for names with copies held, so the map can show one sender heard through several repeaters as one.
        self.sender_paths: dict[str, dict] = {}
        # Your one-tap labels (packet id, or "name|text") -> "spam" / "not_spam", for the replay tool
        self.labels: collections.OrderedDict = collections.OrderedDict()
        self.blocks: dict[str, dict] = {}
        self.suppressed: dict[str, float] = {}
        self.route_suggest: dict[str, dict] = {}   # routes SpamGuard suggests blocking (not saved: re-worked out)
        # Duplicate blocks you removed (or cleared): the copies seen up to then are forgiven, so the next
        # message with that text counts as a first copy again. {text or "w:word|word": time released}
        self.released: dict[str, float] = {}
        self.allow_hops: set[str] = set()
        self.allow_senders: set[str] = set()
        self.allow_texts: set[str] = set()
        self.extra_channels: dict[str, str] = {}
        self.openhop_channels: dict[str, str] = {}
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
        self.reset_at = 0.0   # when "Start again from scratch" was last used
        self.view_marks: dict[str, float] = {}   # lists you cleared on the page: hide what came before
        self.hidden_sources: dict[str, float] = {}   # Spam sources rows you removed (back if spam comes again)
        self.monitor_since = 0.0   # when SpamGuard last went into Monitor (for switching to Protect by itself)
        self.genuine_marks: list[float] = []   # when you last said a message wasn't spam
        self.profiles: dict[str, dict] = {}     # saved settings profiles, by name
        self.profile_in_use: Optional[str] = None
        self.started = time.time()
        self.loop_beat: Optional[float] = None    # end of the last check loop, success or not
        self.loop_count = 0
        self.wake = threading.Event()        # set by the live packet feed to check straight away
        self.live = {"state": "off", "since": None, "packets": 0}
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
        # FloodGuard: every packet heard or sent in the last 15 minutes as (time, airtime ms, flood?, hops,
        # sent by us?, stopped by FloodGuard?), the current limit, and the hops flood packets normally take.
        # Replay guard: recent channel messages, (channel, text) -> (first heard, sender, the sender's own clock)
        self._texts: collections.OrderedDict = collections.OrderedDict()
        self.replays: collections.deque = collections.deque(maxlen=5000)   # when replays were heard
        self.air: collections.deque = collections.deque()
        self._air_mark = 0.0
        # Interference watch: openHop's noise-floor samples (time, dBm) for the last hour, the hours' medians
        # live in hist ("nf"), and the current episode / past episodes in self.jam.
        self.nf: collections.deque = collections.deque()
        self._nf_hour: dict[str, list] = {}
        self.jam: dict = {"mark": 0.0, "since": None, "peak": 0.0, "above_since": 0.0, "below_since": 0.0,
                          "episodes": [], "backfilled": 0.0, "fetched": 0.0}
        self._hop_pending: collections.deque = collections.deque(maxlen=20000)
        self.fg: dict = {"limit": None, "since": 0.0, "last_step": 0.0, "mark": 0.0, "peak": 0.0, "episodes": 0,
                         "busy_since": 0.0, "calm_since": 0.0, "v61": 1}
        self.fg_hops: dict[str, dict[int, int]] = {}   # hour -> {hop count: flood packets} outside floods
        self.fg_adv: dict[str, dict[int, int]] = {}    # the same for adverts only
        # The same counts for every hour, flood or not, kept for two days. Used only when a repeater is so busy
        # that it has too few quiet hours to learn from (the stores above), as on a busy mesh.
        self.fg_hops_all: dict[str, dict[int, int]] = {}
        self.fg_adv_all: dict[str, dict[int, int]] = {}
        self.fg["learnt"] = {}
        self.radio: dict = {}         # openHop's radio settings, for airtime
        self.me: dict = {}            # this repeater: name, hash, location
        self.repeaters: dict = {"ts": 0, "list": []}   # repeaters openHop has heard adverts from
        # Routes that repeater adverts took to reach us: "PUBKEY|A>B>C" -> [count, last seen, lat, lon, name].
        # An advert says exactly where it started, so these teach SpamGuard which repeater each route
        # code really is in each part of the mesh. Not saved: openHop keeps a week of packets, which
        # are read back after each start (backfill_adverts).
        self.adv_routes: dict[str, list] = {}
        self._adv_seen: collections.OrderedDict = collections.OrderedDict()
        self._adv_stamp = 0
        self._adv_backfill = 0.0   # when the last week of adverts was last read from openHop (0 = not yet)
        self.public_reps: dict = {"ts": 0, "list": [], "error": None}  # from the public MeshCore map (optional)
        self._public_busy = False
        self.rule_ids: dict[str, int] = {}   # ids of shared rules (e.g. "let known people through")
        # What openHop actually did with each channel message, from its packet records (every copy):
        # packet hash -> [any copy transmitted, any copy dropped by a policy rule]
        self.verdict: collections.OrderedDict[str, list] = collections.OrderedDict()
        self.cfg: dict[str, Any] = {}
        self._load_state()
        self.rebuild_cfg()
        self._load_public_reps()
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

    def current_level(self) -> int:
        """The protection level: set on the page, else in the config file; an older sensitivity choice
        (relaxed, balanced or strict) stands for 0, 50 or 100."""
        for src in (self.settings, self.file_cfg):
            if src.get("level") is not None:
                try:
                    return max(0, min(100, int(src["level"])))
                except (TypeError, ValueError):
                    pass
            if src.get("sensitivity") in SENSITIVITY_LEVEL:
                return SENSITIVITY_LEVEL[src["sensitivity"]]
        return 50

    def own_level_values(self) -> list[dict]:
        """Values the protection level would set that you have set yourself to something else."""
        lv = level_values(self.cfg.get("level", 50))
        out = []
        for k, v in lv.items():
            mine = self.settings.get(k, self.file_cfg.get(k))
            if mine is not None and mine != v:
                out.append({"key": k, "label": META_BY_KEY[k]["label"], "yours": mine, "level": v,
                            "unit": META_BY_KEY[k].get("unit")})
        return out

    # ---- configuration layering: defaults < protection level < config file < web page
    def rebuild_cfg(self):
        level = self.current_level()
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))
        cfg.update(level_values(level))
        cfg.update(self.file_cfg)
        cfg.update(self.settings)
        cfg["level"] = level
        cfg["sensitivity"] = level_sensitivity(level)
        # FloodGuard's learnt values, for the settings you haven't set yourself
        for k, v in ((getattr(self, "fg", None) or {}).get("learnt") or {}).items():
            if k in FG_AUTO_KEYS and k not in self.settings and k not in self.file_cfg:
                cfg[k] = v
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
                     "path": e.path, "hops": len(e.path), "name_score": e.name_score, "random": e.random, "garbage": e.garbage,
                     "obfuscated": e.obfuscated, "trusted": e.sender in self.allow_senders, "known": self.is_known(e.sender),
                     "known_then": e.known_then, "in_passing": e.in_passing, "exempt": e.exempt, "own": self.is_own(e),
                     "sender_count_24h": h.get("count"), "sender_first_seen": round(h.get("first", e.ts), 2),
                     "campaign_senders": len(cc["senders"]) if cc else 0,
                     "origin_known": bool(e.path) and self.known_origin(e.first_hop),
                     "seen_after_s": round(e.seen_at - e.ts, 1),
                     "caught_by": e.matched, "caught_kind": b["kind"] if b else None,
                     "openhop_forwarded": (self.verdict.get(e.packet) or [None, None])[0],
                     "openhop_policy_dropped": (self.verdict.get(e.packet) or [None, None])[1],
                     "caught_source": b.get("source") if b else None,
                     "mode": "paused" if self.cfg.get("paused") else self.cfg["mode"]})

    def snapshot_settings(self, why: str):
        self.ev({"type": "settings", "why": why, "version": VERSION,
                 "sensitivity": self.cfg["sensitivity"], "level": self.cfg.get("level"), "mode": self.cfg["mode"],
                 "paused": bool(self.cfg.get("paused")),
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
        self.released = {k: v for k, v in st.get("released", {}).items() if v > now - 86400}
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
        fg = st.get("floodguard") or {}
        if isinstance(fg, dict):
            self.fg.update({k: v for k, v in fg.items() if k in ("limit", "since", "last_step", "mark", "peak", "episodes", "learn_start", "ready", "learnt", "learnt_at", "welcomed", "relearn", "v61", "busy_site")})
            if not isinstance(self.fg.get("learnt"), dict):
                self.fg["learnt"] = {}
            self.fg_hops = {k: {int(h): int(n) for h, n in v.items()} for k, v in (fg.get("hops") or {}).items()
                            if isinstance(v, dict) and int(k) > now - 8 * 86400}
            self.fg_adv = {k: {int(h): int(n) for h, n in v.items()} for k, v in (fg.get("adv") or {}).items()
                           if isinstance(v, dict) and int(k) > now - 8 * 86400}
            self.fg_hops_all = {k: {int(h): int(n) for h, n in v.items()} for k, v in (fg.get("hops_all") or {}).items()
                                if isinstance(v, dict) and int(k) > now - 2 * 86400}
            self.fg_adv_all = {k: {int(h): int(n) for h, n in v.items()} for k, v in (fg.get("adv_all") or {}).items()
                               if isinstance(v, dict) and int(k) > now - 2 * 86400}
        if not fg.get("v61") if isinstance(fg, dict) else True:
            # 6.1 learns FloodGuard's values from this repeater's own traffic: values set by hand in 6.0
            # are cleared once, so it starts from its own. Whether FloodGuard is on or off is kept.
            fg_keys = [m["key"] for m in SETTINGS_META if m["group"] == "FloodGuard" and m["key"] != "floodguard"]
            cleared = [k for k in fg_keys if k in self.settings]
            for k in cleared:
                self.settings.pop(k, None)
            if cleared:
                self.activity.appendleft({"ts": now, "msg": "FloodGuard now learns its own settings from this repeater's traffic, "
                                          "so the FloodGuard values set in 6.0 were cleared. You can set them again on the "
                                          "FloodGuard page once it has learnt."})
        self.fg["v61"] = 1
        jm = st.get("interference") or {}
        if isinstance(jm, dict):
            self.jam.update({k: v for k, v in jm.items() if k in ("mark", "since", "peak", "episodes", "backfilled")})
            self.jam["episodes"] = [e for e in (self.jam.get("episodes") or []) if isinstance(e, dict)][-50:]
        self.reset_at = float(st.get("reset_at") or 0)
        self.monitor_since = float(st.get("monitor_since") or 0)
        self.view_marks = {k: float(v) for k, v in (st.get("view_marks") or {}).items()}
        self.hidden_sources = {k: float(v) for k, v in (st.get("hidden_sources") or {}).items() if float(v) > now - 8 * 86400}
        self.genuine_marks = [float(t) for t in (st.get("genuine_marks") or []) if float(t) > now - 7 * 86400]
        self.profiles = {k: v for k, v in (st.get("profiles") or {}).items() if isinstance(v, dict)}
        self.profile_in_use = st.get("profile_in_use") if st.get("profile_in_use") in self.profiles else None
        self.held.extend(h for h in (st.get("held") or []) if isinstance(h, dict) and h.get("ts", 0) > now - 86400)
        for name, v in (st.get("senders") or {}).items():
            if isinstance(v, list) and len(v) == 2 and v[0] > now - 86400:
                self.sender_history[name] = {"first": v[0], "count": int(v[1]), "hops": set()}
        for k, v in (st.get("slow_sends") or {}).items():
            if isinstance(v, dict) and v.get("who") and isinstance(v.get("ts"), list):
                ts = [float(t) for t in v["ts"] if float(t) > now - 172800]
                if ts:
                    self.slow_sends[k] = {"who": str(v["who"]), "ch": v.get("ch"), "snip": str(v.get("snip") or ""), "ts": ts[-40:]}
        for k, v in (st.get("name_links") or {}).items():
            if isinstance(v, dict) and isinstance(v.get("after"), list) and float(v.get("ts") or 0) > now - 8 * 86400:
                self.name_links[str(k)] = {"after": [str(x) for x in v["after"]][:10], "ts": float(v["ts"])}
        day8 = now - 8 * 86400
        for k, v in (st.get("sender_paths") or {}).items():
            if isinstance(v, dict):
                d = {str(pk): {str(dk): int(dn) for dk, dn in pv.items() if float(dk) > day8}
                     for pk, pv in v.items() if isinstance(pv, dict)}
                d = {pk: pv for pk, pv in d.items() if pv}
                if d:
                    self.sender_paths[str(k)] = d
        for k, v in (st.get("held_names") or {}).items():
            if isinstance(v, dict):
                d = {str(dk): [int(x) for x in dv][:2] for dk, dv in v.items()
                     if isinstance(dv, list) and len(dv) == 2 and float(dk) > day8}
                if d:
                    self.held_names[str(k)] = d
        for k, v in (st.get("labels") or {}).items():
            if v in ("spam", "not_spam"):
                self.labels[str(k)] = v
        if isinstance(st.get("level_preview"), dict):
            self.level_preview = st["level_preview"]
            self._preview_tried = float(self.level_preview.get("ran") or self.level_preview.get("failed") or 0)
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
                json.dump(self.state_dict(), f, separators=(",", ":"))   # compact: less to write each time
            os.replace(tmp, path)
        except Exception as e:
            log.warning("Could not save state: %s", e)

    def state_dict(self) -> dict:
        """Everything SpamGuard has learnt, as saved to its state file (and handed to the plugin when moving)."""
        now = time.time()
        return {
                    "version": VERSION,
                    "blocks": self.blocks,
                    "suppressed": self.suppressed,
                    "released": self.released,
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
                    "interference": {k: self.jam.get(k) for k in ("mark", "since", "peak", "episodes", "backfilled")},
                    "floodguard": {**{k: self.fg.get(k) for k in ("limit", "since", "last_step", "mark", "peak", "episodes", "learn_start", "ready", "learnt", "learnt_at", "welcomed", "relearn", "v61", "busy_site")},
                                   "hops": self.fg_hops, "adv": self.fg_adv,
                                   "hops_all": self.fg_hops_all, "adv_all": self.fg_adv_all},
                    "reset_at": getattr(self, "reset_at", 0.0),
                    "monitor_since": getattr(self, "monitor_since", 0.0),
                    "view_marks": getattr(self, "view_marks", {}),
                    "hidden_sources": getattr(self, "hidden_sources", {}),
                    "genuine_marks": getattr(self, "genuine_marks", [])[-50:],
                    "profiles": self.profiles, "profile_in_use": self.profile_in_use,
                    "rule_ids": self.rule_ids,
                    "senders": {k: [round(v["first"], 1), v["count"]]
                                for k, v in list(self.sender_history.items())[-3000:]},
                    "name_links": self.name_links,
                    "held_names": dict(list(self.held_names.items())[-3000:]),
                    "sender_paths": dict(list(self.sender_paths.items())[-self.SENDER_PATHS_MAX:]),
                    "labels": dict(list(self.labels.items())[-1000:]),
                    "level_preview": self.level_preview,
                    "slow_sends": {k: {"who": v["who"], "ch": v["ch"], "snip": v["snip"], "ts": [round(t, 1) for t in v["ts"][-40:]]}
                                   for k, v in list(self.slow_sends.items())[-1500:]},
                }

    def reset_all(self):
        """Back to a fresh install, keeping only Monitor/Protect and channels you added. Nothing recorded is
        thrown away (activity, charts and the evidence log are all kept), but the page only shows what
        happens after the reset, so old and new don't get mixed up.
        Removed blocks don't wait 24 hours: detection starts again straight away."""
        mode = self.cfg.get("mode", "monitor")
        self.reset_at = time.time()
        n = len(self.blocks)
        self.blocks.clear()
        self.suppressed.clear()
        self.allow_hops.clear()
        self.allow_senders.clear()
        self.allow_texts.clear()
        kept = {k: v for k, v in self.settings.items() if k in KEEP_ON_RESET}
        self.settings = dict(kept, **({"mode": mode} if mode != DEFAULT_CONFIG["mode"] else {}))
        self.routes.clear()
        self.relays.clear()
        self.adv_routes.clear()
        self._adv_stamp += 1
        self.clusters.clear()
        self.held.clear()
        self.rule_ids.clear()
        # FloodGuard starts again too: what it learnt, its flood limit and its learning days. (The noise
        # measurements and recorded interference stay: they're a record, not a setting.)
        self.fg.update(limit=None, learnt={}, learnt_at=None, ready=None, relearn=None, learn_start=None,
                       episodes=0, peak=0.0, start_now=None, welcomed=None)
        self.fg_hops.clear()
        self.fg_adv.clear()
        self._hop_pending.clear()
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
            used.update((b.get("size_ids") or {}).values())
        used.update(self.rule_ids.values())
        while self.next_rule_id in used:
            self.next_rule_id += 1
        rid = self.next_rule_id
        self.next_rule_id += 1
        if self.next_rule_id > RULE_ID_BASE + 90000:
            self.next_rule_id = RULE_ID_BASE
        return rid

    # ---- openHop API ----
    def _api(self, method: str, path: str, body: Optional[dict] = None, timeout: float = 15) -> Any:
        url = self.cfg["openhop_url"].rstrip("/") + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cfg.get("api_key"):
            req.add_header("X-API-Key", self.cfg["api_key"])
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=timeout) as r:
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
        # Never "Unknown": openHop gives that name to every message without a "Name: " prefix.
        return sorted((set(names) | {n for n in self.allow_senders if n}) - {"Unknown"})

    def _held_in_passing(self, e: Event) -> bool:
        """Held only because it passed THROUGH a blocked repeater partway along its route
        (spam starts at the blocked repeater itself)."""
        b = self.blocks.get(e.matched) if e.matched else None
        return bool(b and b["kind"] == "hop" and self.gated(b) and e.path and not self._same_hop(e.path[0], b["value"]))

    def _wrongly_caught_regular(self, e: Event) -> bool:
        """Someone who has chatted for over an hour under a normal-looking name, caught only by a route
        block or a campaign text: keep getting to know them, so one wrong block can't lock regulars out."""
        b = self.blocks.get(e.matched) if e.matched else None
        return bool(b) and b.get("source") in ("rotation", "campaign") and self.established(e.sender) \
            and not (e.random or e.obfuscated or e.garbage)

    def learn_sender(self, e: Event, spam: bool):
        """Count a genuine message towards its sender becoming known."""
        if spam or e.random or e.obfuscated or not e.sender or e.sender in ("?", "Unknown"):
            return
        if e.matched and not self._held_in_passing(e) and not self._wrongly_caught_regular(e):
            return
        for b in self.blocks.values():  # never learn from messages that START at a blocked repeater
            if b["kind"] == "hop" and e.path and self._same_hop(e.path[0], b["value"]):
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

    # ---- FloodGuard ----
    # Floods of encrypted packets with a new identity each time can't be told apart by sender or text, and
    # their routes can be padded. What a sender can't fake is how busy this repeater's own radio is, so
    # FloodGuard measures that from every packet openHop hears and sends (whatever its type), and while
    # flood traffic keeps the radio too busy it stops passing on flood packets that have come a long way.
    FG_WINDOW = 300            # busy is measured over five minutes
    FG_SUSTAIN = 60            # and has to last a minute before FloodGuard steps in
    FG_STEP_SECONDS = 120      # it tightens at most once every two minutes
    FG_MIN_FLOOD_SHARE = 0.6   # only when most of the airtime is flood traffic
    FG_MIN_PACKETS = 20        # and there's enough of it to judge
    FG_DEFAULT_REACH = 15      # longest normal route, until it has learnt this mesh's
    FG_RULE_RE = re.compile(r"^Policy blocked packet \(rule (\d+)")

    def fg_rule_ids(self) -> set:
        return {self.rule_ids[k] for k in ("flood:limit", "flood:unscoped", "flood:advert") if k in self.rule_ids}

    def fg_over(self, hops: int, ptype: int, route: int) -> bool:
        """Whether one of FloodGuard's rules, as they stand now, covers a flood packet."""
        c = self.cfg
        if not c.get("floodguard"):
            return False
        lim = self.fg.get("limit")
        u, a = int(c.get("flood_max_unscoped") or 0), int(c.get("flood_max_advert") or 0)
        return bool((lim and hops >= lim) or (u and route == ROUTE_FLOOD and hops >= u)
                    or (a and ptype == PAYLOAD_TYPE_ADVERT and hops >= a))

    def fg_observe(self, p: dict):
        """One packet openHop heard or sent: the airtime it took (twice if this repeater passed it on),
        whether it was a flood packet, how far it had come, and whether a FloodGuard rule stopped it.
        Each packet is counted once, also across restarts."""
        try:
            ts = float(p.get("timestamp") or 0)
            length, route, ptype = int(p.get("length") or 0), int(p.get("route", -1)), int(p.get("type", -1))
        except (TypeError, ValueError):
            return
        counted = ts <= self.fg["mark"]       # already in the hourly counts before a restart
        if counted and ts <= self._air_mark:
            return
        self._air_mark = max(self._air_mark, ts)
        ms = self.airtime_ms(length) if length > 0 else 0.0
        sent = bool(p.get("transmitted"))
        if "tx failed" in str(p.get("drop_reason") or "").lower():
            self.tx_fails.append(ts)       # openHop tried to send and the radio didn't
        elif sent:
            self.tx_ok_at = max(self.tx_ok_at or 0.0, ts)
            self.tx_oks.append(ts)
        local = "rssi" in p and not p.get("rssi") and not p.get("snr") and not p.get("rx_radio_id")
        on_air = ms if local else ms * (2 if sent else 1)
        flood = route in (ROUTE_TRANSPORT_FLOOD, ROUTE_FLOOD)
        hops = len(parse_path(p.get("original_path")))
        m = self.FG_RULE_RE.match(str(p.get("drop_reason") or ""))
        stopped = bool(m) and int(m.group(1)) in self.fg_rule_ids()
        wd_stopped = bool(m) and int(m.group(1)) in self.wardrive_rule_ids()
        wd_heard = False
        if ptype == PAYLOAD_TYPE_GRP_TXT and self.cfg.get("wardrive_block") and not local:
            try:
                first = int(str(p.get("payload") or "")[:2], 16)
                wd_heard = any(channel_hash_byte(k) == first for k in self.wardrive_channels().values())
            except ValueError:
                pass
        self.air.append((ts, on_air, flood))
        if counted:
            return
        self.fg["mark"] = ts
        hour = str(int(ts // 3600 * 3600))
        h = self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})
        h["ar"] = round(h.get("ar", 0) + on_air)
        if not local:
            h["pk"] = h.get("pk", 0) + 1
        if flood:
            h["af"] = round(h.get("af", 0) + on_air)
        if wd_heard or wd_stopped:
            h["wh"] = h.get("wh", 0) + 1
        if wd_stopped:
            h["ws"] = h.get("ws", 0) + 1
        if stopped:
            h["fc"] = h.get("fc", 0) + 1
            h["fs"] = round(h.get("fs", 0) + ms)
            path = parse_path(p.get("original_path"))
            if path:   # the first repeater on the route: where the flood came into the mesh
                fh = h.setdefault("fh", {})
                if path[0] in fh or len(fh) < 60:
                    fh[path[0]] = fh.get(path[0], 0) + 1
        elif flood and sent and not local and self.fg_over(hops, ptype, route):
            h["fx"] = h.get("fx", 0) + 1   # over a limit but passed on: Monitor, or before the rule landed
        if flood and not local:
            # Learnt only once it's clear the radio wasn't flooded at the time (see fg_decide).
            self._hop_pending.append((ts, hour, hops, ptype == PAYLOAD_TYPE_ADVERT))

    def fg_can_act(self) -> bool:
        """FloodGuard holds packets back only once it has finished its first learning AND knows how far flood
        packets normally come on this repeater (or you set the lowest hop limit yourself). Until then it only
        counts, because a made-up guess can be shorter than a busy mesh's ordinary routes."""
        return bool(self.fg.get("ready")) and (self.fg_reach() is not None or "flood_hop_floor" in self.settings)

    def fg_load(self, now: float) -> tuple[float, float, int]:
        """(% of the last five minutes the radio was busy, share of that which was flood traffic, flood packets)."""
        while self.air and self.air[0][0] < now - 900:
            self.air.popleft()
        tot = fl = 0.0
        n = 0
        for ts, ms, flood in self.air:
            if now - self.FG_WINDOW <= ts <= now:
                tot += ms
                if flood:
                    fl += ms
                    n += 1
        return min(100.0, 100.0 * tot / (self.FG_WINDOW * 1000)), (fl / tot if tot else 0.0), n

    def _fg_compact(self, now: float):
        """Route counts older than a day and a bit are folded into one entry per day (the last day stays
        hourly for fg_reach). Only calm traffic is ever stored, so the learnt values come out the same, and
        the state file written to the SD card stays small."""
        cut = now - 26 * 3600
        for store in (self.fg_hops, self.fg_adv):
            for k in [k for k in store if int(k) < cut and int(k) % 86400]:
                day = str(int(k) // 86400 * 86400)
                merged = store.setdefault(day, {})
                for h, n in store.pop(k).items():
                    merged[h] = merged.get(h, 0) + n
            for k in [k for k in store if int(k) < now - 8 * 86400]:
                del store[k]
        for store in (self.fg_hops_all, self.fg_adv_all):
            for k in [k for k in store if int(k) < now - 2 * 86400]:
                del store[k]

    def fg_reach(self) -> Optional[int]:
        """How many hops nearly all (95%) flood packets have travelled when they reach this repeater on an
        ordinary day, from the last 24 hours outside floods. None until it has heard enough to say."""
        now = time.time()
        cut = now - 86400
        quiet = 0.7 * float(self.cfg.get("flood_busy_percent") or 15)
        counts: dict[int, int] = {}
        self._fg_compact(now)
        for k, v in list(self.fg_hops.items()):
            if int(k) < now - 8 * 86400:
                del self.fg_hops[k]
            # Hours with a flood in them (or this hour, which may be starting one) don't say what's normal.
            elif int(k) >= cut - 3600 and float((self.hist.get(k) or {}).get("bz") or 0) < quiet:
                for hops, n in v.items():
                    counts[hops] = counts.get(hops, 0) + n
        total = sum(counts.values())
        q = 0.95
        self.fg["reach_all"] = False
        if total < 200:
            # Too few quiet hours: a repeater that is busy most of the time (where long routes are often normal
            # and the radio is rarely below the quiet line). Take every hour of the last day instead, and a
            # little lower in the range so that a flood's padded routes can't pull it up much.
            counts = {}
            for k, v in list(self.fg_hops_all.items()):
                if int(k) >= cut - 3600:
                    for hops, n in v.items():
                        counts[hops] = counts.get(hops, 0) + n
            total = sum(counts.values())
            if total < 200:
                return None
            q = 0.90
            self.fg["reach_all"] = True
        run = 0
        for hops in sorted(counts):
            run += counts[hops]
            if run >= q * total:
                return hops
        return max(counts)

    def fg_decide(self, now: Optional[float] = None) -> bool:
        """Start, tighten or lift the flood limit. True when openHop's rules need to change."""
        now = now or time.time()
        c, f = self.cfg, self.fg
        if not self.airtime_ms(40):
            f["busy_now"] = None
            return False
        busy, share, n = self.fg_load(now)
        f["busy_now"], f["share_now"] = round(busy, 1), round(share, 2)
        # How busy the radio got, per hour, for the Overview (measured whether FloodGuard is on or not).
        if self.air:
            h = self.hist.setdefault(str(int(now // 3600 * 3600)), {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})
            h["bz"] = max(float(h.get("bz") or 0), round(busy, 1))
        # How far flood packets normally come: learnt from packets heard at least five minutes ago, and
        # only while the radio is quiet, so a flood's padded routes never count as normal.
        calm = busy < 0.7 * float(c.get("flood_busy_percent") or 15) and not f.get("limit")
        while self._hop_pending and self._hop_pending[0][0] < now - self.FG_WINDOW:
            _, hour, hops, advert = self._hop_pending.popleft()
            for store in (self.fg_hops_all, self.fg_adv_all) if advert else (self.fg_hops_all,):
                hh = store.setdefault(hour, {})
                hh[hops] = hh.get(hops, 0) + 1
            if calm:
                for store in (self.fg_hops, self.fg_adv) if advert else (self.fg_hops,):
                    hh = store.setdefault(hour, {})
                    hh[hops] = hh.get(hops, 0) + 1
        if not c.get("floodguard"):
            if f.get("limit"):
                f["limit"] = None
                self.note("FloodGuard is off, so its flood limit was removed")
                return True
            return False
        learnt = self.fg_learn(now)   # may set this mesh's own level and limits
        level, floor = float(c["flood_busy_percent"]), int(c["flood_hop_floor"])
        flooding = busy >= level and share >= self.FG_MIN_FLOOD_SHARE and n >= self.FG_MIN_PACKETS
        # The busier the radio, the tighter: two hops less for every five points above the level.
        reach = self.fg_reach()
        start = max(floor, (reach if reach is not None else self.FG_DEFAULT_REACH) + 1)
        target = max(floor, start - 2 * int((busy - level) // 5)) if flooding else None
        changed = learnt
        can = self.fg_can_act()
        if "can_act" in f and can != f["can_act"]:   # started or stopped being able to hold packets back: rules change between log-only and drop
            changed = True
        f["can_act"] = can
        if flooding:
            f["calm_since"] = 0.0
            f["busy_since"] = f.get("busy_since") or now
            if not f.get("limit"):
                if now - f["busy_since"] >= self.FG_SUSTAIN:
                    # Starts just past the routes it normally hears, then tightens a step at a time.
                    f.update(limit=start, since=now, last_step=now, peak=busy, episodes=int(f.get("episodes") or 0) + 1)
                    acting = c["mode"] == "protect" and not c.get("paused") and self.fg_can_act()
                    self.note(f"FloodGuard: the radio is {busy:.0f}% busy, {share:.0%} of it flood traffic. "
                              + (f"Flood packets that have already come {start} or more hops are not passed on until it calms down."
                                 if acting else
                                 f"Flood packets from {start} or more hops would be held back, but "
                                 + ("FloodGuard is still learning" if not f.get("ready") else
                                    "FloodGuard hasn't yet heard enough traffic to know how far packets normally come"
                                    if c["mode"] == "protect" and not c.get("paused") else "SpamGuard is in Monitor")
                                 + ", so it only counts them and passes everything on."))
                    changed = True
            elif target < f["limit"] and now - f["last_step"] >= self.FG_STEP_SECONDS:
                f.update(limit=max(target, f["limit"] - 2), last_step=now)
                acting = c["mode"] == "protect" and not c.get("paused") and self.fg_can_act()
                self.note(f"FloodGuard: still {busy:.0f}% busy, so flood packets from {f['limit']} or more hops away are now "
                          + ("held back too." if acting else "counted too (nothing is held back yet)."))
                changed = True
            if f.get("limit"):
                f["peak"] = max(float(f.get("peak") or 0), busy)
        else:
            f["busy_since"] = 0.0
            if f.get("limit"):
                if busy < level * 0.7:
                    f["calm_since"] = f.get("calm_since") or now
                    if now - f["calm_since"] >= int(c["flood_calm_minutes"]) * 60:
                        mins = max(1, round((now - float(f.get("since") or now)) / 60))
                        self.note(f"FloodGuard: the radio is quiet again ({busy:.0f}% busy, at most {float(f.get('peak') or 0):.0f}%), "
                                  f"so the flood limit was lifted after {mins} minutes.")
                        f.update(limit=None, calm_since=0.0)
                        changed = True
                else:
                    f["calm_since"] = 0.0
        if changed and (not f.get("limit") or f.get("since") == now):
            self._important = True   # started or lifted: save now. A step tighter waits for the next 5-minute save.
        return changed

    # ---- FloodGuard learning: how busy this radio normally gets and how far packets normally come
    @staticmethod
    def _quantile(counts: dict, q: float) -> Optional[int]:
        total = sum(counts.values())
        run = 0
        for h in sorted(counts):
            run += counts[h]
            if run >= q * total:
                return h
        return max(counts) if counts else None

    def fg_learnt_values(self, now: float) -> dict:
        """What the last week of calm traffic says the automatic settings should be (only those it has
        heard enough to judge), each kept inside its safe range."""
        c = self.cfg
        cut = max(now - 7 * 86400, float(self.fg.get("learn_start") or 0))   # nothing from before a re-learn
        level = float(c.get("flood_busy_percent") or 15)
        def calm(k):
            return float((self.hist.get(k) or {}).get("bz") or 0) < 0.7 * level and not (self.hist.get(k) or {}).get("fc")
        busy = sorted(float(v["bz"]) for k, v in self.hist.items()
                      if int(k) >= cut and v.get("bz") is not None and float(v["bz"]) < level and not v.get("fc"))
        def merged(store):
            out: dict[int, int] = {}
            for k, v in store.items():
                if int(k) >= cut and calm(k):
                    for h, n in v.items():
                        out[h] = out.get(h, 0) + n
            return out
        hops, adv = merged(self.fg_hops), merged(self.fg_adv)
        # Too few quiet hours (a busy repeater): learn the route limits from every hour of the last two days.
        def every(store):
            return {h: sum(v.get(h, 0) for k, v in store.items() if int(k) >= cut)
                    for h in {h for k, v in store.items() if int(k) >= cut for h in v}}
        if sum(hops.values()) < 500:
            hops = every(self.fg_hops_all)
        if sum(adv.values()) < 50:
            adv = every(self.fg_adv_all)
        new = {}
        if len(busy) >= 48:   # two days of hours, busiest five minutes of each
            # Twice a normal busy hour, and comfortably above the busiest genuine five minutes it heard.
            new["flood_busy_percent"] = round(max(2 * busy[int(0.9 * (len(busy) - 1))], 1.25 * busy[int(0.99 * (len(busy) - 1))]))
            self.fg.pop("busy_site", None)
        else:
            # Hours below the limit were too few to judge. That is what a repeater in a busy place looks like
            # (the radio sits above the starting limit most of the time), and it would never learn a higher
            # limit if only quiet hours counted. So take every hour and use the middle one, which a flood that
            # lasts a few hours can't move. Twice a typical hour, as above.
            # Hours FloodGuard flagged as a flood are left out, and if flood hours are most of what it heard, it
            # learns nothing at all from them (a flood that long must not become "normal"). The busy limit it
            # sets this way stops at BUSY_SITE_CEILING, below the top of the usual range.
            window = [v for k, v in self.hist.items() if int(k) >= cut and v.get("bz") is not None]
            every = sorted(float(v["bz"]) for v in window if not v.get("fc"))
            flood_share = 1 - len(every) / len(window) if window else 0
            if len(every) >= 48 and flood_share <= 0.5:
                new["flood_busy_percent"] = min(self.BUSY_SITE_CEILING, round(2 * every[len(every) // 2]))
                self.fg["busy_site"] = True
            else:
                self.fg.pop("busy_site", None)
        if sum(hops.values()) >= 500:
            new["flood_max_unscoped"] = 2 * self._quantile(hops, 0.99)
        if sum(adv.values()) >= 50:
            new["flood_max_advert"] = self._quantile(adv, 0.99) + 2
        return {k: max(FG_AUTO_KEYS[k][0], min(FG_AUTO_KEYS[k][1], int(v))) for k, v in new.items()}

    BUSY_SITE_CEILING = 30   # a limit learnt on a permanently busy radio never goes above this (the usual range reaches 40)
    FG_DAILY_STEP = {"flood_busy_percent": 5, "flood_max_unscoped": 4, "flood_max_advert": 2}

    def fg_learn(self, now: float) -> bool:
        """Three days of learning first (FloodGuard only counts meanwhile), then the automatic settings
        are set from what this repeater heard, and checked again once a day, moving a little at a time.
        A setting you set yourself is never changed. True when openHop's rules need to change."""
        f, c = self.fg, self.cfg
        if not f.get("learn_start"):
            f["learn_start"] = now
            if not f.get("welcomed"):
                f["welcomed"] = 1
                self.note(f"FloodGuard is on. For the next {FG_LEARN_DAYS} days it learns how busy this repeater's radio "
                          "normally gets and how far packets normally travel, and only counts what it would stop. Then it "
                          "sets its limits from that and starts acting. You can turn it off on the FloodGuard page.")
        relearn = bool(f.get("relearn"))
        if (not f.get("ready") or relearn) and now - float(f["learn_start"]) < FG_LEARN_DAYS * 86400:
            return False
        if f.get("learnt_at") and now - float(f["learnt_at"]) < 86400:
            return False
        new = self.fg_learnt_values(now)
        first = not f.get("ready") or relearn
        if first and not new and now - float(f["learn_start"]) < 7 * 86400 and not f.get("start_now"):
            return False   # heard too little to judge yet: keep learning, for up to a week
        learnt = f.setdefault("learnt", {})
        if not first:   # after the first time (or a fresh start), small daily steps only
            for k, v in list(new.items()):
                old = learnt.get(k, DEFAULT_CONFIG[k])
                step = self.FG_DAILY_STEP[k]
                new[k] = max(old - step, min(old + step, v))
        auto = {k: v for k, v in new.items() if k not in self.settings}
        changed = {k: v for k, v in auto.items() if learnt.get(k) != v}
        learnt.update(new)
        f["learnt_at"] = now
        f.pop("start_now", None)
        words = {"flood_busy_percent": lambda v: f"steps in above {v}% busy",
                 "flood_max_unscoped": lambda v: f"flood packets with no region stop after {v} hops",
                 "flood_max_advert": lambda v: f"adverts stop after {v} hops"}
        if first and relearn:
            f.pop("relearn", None)
            what = "; ".join(words[k](auto.get(k, self.cfg.get(k))) for k in FG_AUTO_KEYS if k in auto)
            self.note(f"FloodGuard has learnt this repeater's traffic again: {what or 'too little traffic to learn from, so it keeps the recommended values'}.")
        elif first:
            f["ready"] = now
            what = "; ".join(words[k](self.cfg.get(k) if k in self.settings else auto.get(k, c.get(k)))
                             + (" (yours)" if k in self.settings else "" if k in auto else " (recommended)") for k in FG_AUTO_KEYS)
            self.note(f"FloodGuard has learnt this repeater's traffic and now acts: {what}. Settings you set yourself are kept"
                      + ("." if new else ". It heard too little to learn from, so it uses the recommended values.")
                      + (" The radio here is busy most of the time, so it set its busy limit from that rather than from quiet hours." if f.get("busy_site") and "flood_busy_percent" in auto else ""))
        elif changed:
            self.note("FloodGuard adjusted to this mesh's recent traffic: " + "; ".join(words[k](v) for k, v in changed.items()) + ".")
        self.rebuild_cfg()
        self._important = True
        return True

    # ---- Interference watch ----
    JAM_SUSTAIN = 300      # the rise has to last five minutes
    JAM_CLEAR = 600        # and be gone for ten before an episode ends

    def nf_ingest(self, rows: list):
        """openHop's noise-floor samples (oldest first). On a node with several radios, only the busiest
        radio's samples are used, so two receivers on two bands aren't mixed."""
        rids = collections.Counter(r.get("radio_id") for r in rows if isinstance(r, dict))
        rid = rids.most_common(1)[0][0] if rids else None
        for r in rows:
            try:
                ts, v = float(r["timestamp"]), float(r["noise_floor_dbm"])
            except (KeyError, TypeError, ValueError):
                continue
            if r.get("radio_id") != rid or ts <= self.jam["mark"] or not -160 < v < -20:
                continue
            self.jam["mark"] = ts
            self.nf.append((ts, v))
            hour = str(int(ts // 3600 * 3600))
            raw = self._nf_hour.setdefault(hour, [])
            raw.append(v)
            h = self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})
            h["nf"] = round(statistics.median(raw), 1)
            h["nfx"] = round(max(float(h.get("nfx", -999)), v), 1)
        cut = time.time() - 3600
        while self.nf and self.nf[0][0] < cut:
            self.nf.popleft()
        for k in [k for k in self._nf_hour if int(k) < cut - 3600]:
            del self._nf_hour[k]

    def fetch_noise(self):
        """New samples every two minutes; once at start, the last week in the background (for the baseline)."""
        now = time.time()
        if not self.cfg.get("interference_watch", True) or now - self.jam.get("fetched", 0) < 120:
            return
        self.jam["fetched"] = now
        if now - float(self.jam.get("backfilled") or 0) > 6 * 86400 and not getattr(self, "_nf_busy", False):
            self._nf_busy = True
            def work():
                try:
                    res = self._api("GET", "/api/noise_floor_history?hours=168&limit=25000", timeout=60)
                    rows = res.get("data", res) if isinstance(res, dict) else res
                    if isinstance(rows, dict):
                        rows = rows.get("history") or rows.get("data") or []
                    with self.lock:
                        self.nf_ingest(rows or [])
                        self.jam["backfilled"] = time.time()
                except Exception as e:
                    log.debug("noise floor history not available: %s", e)
                finally:
                    self._nf_busy = False
            threading.Thread(target=work, daemon=True).start()
            return
        try:
            res = self._api("GET", "/api/noise_floor_history?hours=1&limit=400", timeout=15)
            rows = res.get("data", res) if isinstance(res, dict) else res
            if isinstance(rows, dict):
                rows = rows.get("history") or rows.get("data") or []
            with self.lock:
                self.nf_ingest(rows or [])
        except Exception as e:
            log.debug("noise floor not available: %s", e)

    def nf_baseline(self, now: float) -> Optional[float]:
        """This site's normal noise level: the median of the hourly medians over the last week, leaving out
        hours with interference and the current hour. None until there are at least six hours."""
        this_hour = int(now // 3600 * 3600)
        vals = [float(v["nf"]) for k, v in self.hist.items()
                if v.get("nf") is not None and not v.get("ie") and now - 7 * 86400 <= int(k) < this_hour]
        return round(statistics.median(vals), 1) if len(vals) >= 6 else None

    def nf_now(self, now: float) -> Optional[float]:
        vals = [v for ts, v in self.nf if now - 300 <= ts <= now]
        return round(statistics.median(vals), 1) if len(vals) >= 5 else None

    @staticmethod
    def range_share(db: float) -> int:
        """Roughly how much of its normal hearing range a receiver keeps with this much extra noise."""
        return max(1, min(100, round(100 * 10 ** (-max(0.0, db) / 20))))

    def jam_decide(self, now: Optional[float] = None) -> None:
        now = now or time.time()
        j, c = self.jam, self.cfg
        if not c.get("interference_watch", True):
            return
        base, cur = self.nf_baseline(now), self.nf_now(now)
        j["baseline"], j["current"] = base, cur
        if base is None or cur is None:
            return
        rise, level = cur - base, float(c.get("interference_db") or 10)
        freq = (self.radio or {}).get("frequency")
        on = f" on {float(freq) / 1e6:.3f} MHz" if isinstance(freq, (int, float)) and freq > 1e6 else \
            (f" on {float(freq):.3f} MHz" if isinstance(freq, (int, float)) and freq else "")
        hour = str(int(now // 3600 * 3600))
        # A flood also lifts the measured noise (packets on air), but then the radio is busy with traffic it
        # can decode; a carrier drowns traffic instead. So a flood being contained doesn't count.
        flooding = bool(self.fg.get("limit")) or float(self.fg.get("busy_now") or 0) >= float(c.get("flood_busy_percent") or 15)
        if not j.get("since"):
            if rise >= level and not flooding:
                j["above_since"] = j.get("above_since") or now
                if now - j["above_since"] >= self.JAM_SUSTAIN:
                    j.update(since=j["above_since"], peak=rise, below_since=0.0)
                    self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})["ie"] = 1
                    self.note(f"Interference: the noise{on} has been {rise:.0f} dB above normal for five minutes "
                              f"({cur:.0f} dBm against a normal {base:.0f} dBm). This repeater can only hear about "
                              f"{self.range_share(rise)}% as far as usual. A nearby transmitter that never stops, such as "
                              "faulty or non-compliant equipment, or jamming, usually causes this.")
                    self._important = True
            else:
                j["above_since"] = 0.0
            return
        # during an episode
        self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})["ie"] = 1
        j["peak"] = max(float(j.get("peak") or 0), rise)
        if rise < level / 2:
            j["below_since"] = j.get("below_since") or now
            if now - j["below_since"] >= self.JAM_CLEAR:
                start, end = float(j["since"]), float(j["below_since"])
                ep = {"start": round(start), "end": round(end), "peak_db": round(float(j["peak"]), 1),
                      "baseline": base, "freq": freq}
                # packets heard during the episode against the same hours on other days
                heard = sum(v.get("pk", 0) for k, v in self.hist.items() if start - 3600 < int(k) <= end)
                hours = max(1, len([k for k in self.hist if start - 3600 < int(k) <= end]))
                usual = [v.get("pk", 0) for k, v in self.hist.items() if not v.get("ie") and v.get("pk") is not None]
                if usual:
                    ep["heard_vs_usual"] = round(100 * (heard / hours) / max(1e-9, statistics.median(usual)))
                j["episodes"] = (j.get("episodes") or [])[-49:] + [ep]
                mins = max(1, round((end - start) / 60))
                self.note(f"Interference over: the noise{on} was raised for {mins} minutes, at most {ep['peak_db']:.0f} dB "
                          f"above normal. Recorded with its times on the FloodGuard page.")
                j.update(since=None, peak=0.0, above_since=0.0, below_since=0.0)
                self._important = True
        else:
            j["below_since"] = 0.0

    def jam_status(self) -> dict:
        j = self.jam
        base, cur = j.get("baseline"), j.get("current")
        rise = round(cur - base, 1) if base is not None and cur is not None else None
        return {"enabled": bool(self.cfg.get("interference_watch", True)), "baseline": base, "current": cur, "rise": rise,
                "range": self.range_share(rise) if rise is not None else None, "level": self.cfg.get("interference_db"),
                "since": j.get("since"), "peak": round(float(j.get("peak") or 0), 1) if j.get("since") else None,
                "learning": base is None, "episodes": list(reversed(j.get("episodes") or []))[:20],
                "freq": (self.radio or {}).get("frequency")}

    def fg_status(self) -> dict:
        c, f = self.cfg, self.fg
        reach = self.fg_reach()
        ls = float(f.get("learn_start") or 0)
        return {"enabled": bool(c.get("floodguard")), "radio_known": bool(self.airtime_ms(40)),
                "learning": bool(c.get("floodguard")) and (not f.get("ready") or bool(f.get("relearn"))),
                "relearning": bool(f.get("relearn")),
                "acting": bool(c.get("floodguard")) and self.fg_can_act() and c["mode"] == "protect" and not c.get("paused"),
                "waiting_reach": bool(c.get("floodguard")) and bool(f.get("ready")) and reach is None
                                 and "flood_hop_floor" not in self.settings and c["mode"] == "protect" and not c.get("paused"),
                "reach_all": bool(f.get("reach_all")) and reach is not None,
                "learn_start": ls or None, "learn_until": ls + FG_LEARN_DAYS * 86400 if ls else None,
                "learn_days": FG_LEARN_DAYS, "learnt": dict(f.get("learnt") or {}), "learnt_at": f.get("learnt_at"),
                "auto": sorted(k for k in FG_AUTO_KEYS if k not in self.settings and k not in self.file_cfg),
                "busy": f.get("busy_now"), "flood_share": f.get("share_now"), "level": c.get("flood_busy_percent"),
                "limit": f.get("limit") if c.get("floodguard") else None, "since": f.get("since") if f.get("limit") else None,
                "peak": f.get("peak") if f.get("limit") else None, "episodes": int(f.get("episodes") or 0),
                "reach": reach, "floor": c.get("flood_hop_floor"),
                "unscoped": int(c.get("flood_max_unscoped") or 0) if c.get("floodguard") else 0,
                "advert": int(c.get("flood_max_advert") or 0) if c.get("floodguard") else 0,
                "rules": sorted(self.fg_rule_ids()) if c.get("floodguard") and (f.get("limit") or c.get("flood_max_unscoped") or c.get("flood_max_advert")) else []}

    def _held_day(self, e: Event) -> Optional[list]:
        """[messages, copies held] for this name on the day of this message, or None for our own messages."""
        if not e.sender or e.sender == "?" or e.local:
            return None
        day = str(int(time.mktime(time.localtime(e.ts)[:3] + (0, 0, 0, 0, 0, -1))))
        d = self.held_names.get(e.sender)
        if d is None:
            if len(self.held_names) >= 3000:   # forget the names heard longest ago
                old = min(self.held_names, key=lambda n: max(self.held_names[n]))
                del self.held_names[old]
            d = self.held_names[e.sender] = {}
        if day not in d:
            for k in [k for k in d if float(k) < e.ts - 8 * 86400]:
                del d[k]
        return d.setdefault(day, [0, 0])

    SENDER_PATHS_MAX = 300      # names whose routes are remembered for the map
    SENDER_PATH_HOPS = 4        # how much of each route: enough to place where it entered the mesh
    SENDER_MIN_HELD = 2         # copies held over 7 days before a name's routes are remembered

    def repeat_spammer(self, name: str, now: Optional[float] = None) -> bool:
        """A name with at least two copies held in the last 7 days, or one that carried on another name's
        repeat count (or was carried on from). Only used to place them on the map, never to block anything."""
        if not name or name == "?":
            return False
        now = time.time() if now is None else now
        if name in self.name_links or any(name in v.get("after", []) for v in self.name_links.values()):
            return True
        d = self.held_names.get(name) or {}
        return sum(v[1] for k, v in d.items() if float(k) >= now - 7 * 86400) >= self.SENDER_MIN_HELD

    def _note_sender_path(self, e: Event):
        if not e.path or e.local or not self.repeat_spammer(e.sender, e.ts):
            return
        day = str(int(time.mktime(time.localtime(e.ts)[:3] + (0, 0, 0, 0, 0, -1))))
        d = self.sender_paths.pop(e.sender, None) or {}
        self.sender_paths[e.sender] = d        # most recently heard last
        k = ">".join(e.path[:self.SENDER_PATH_HOPS])
        if k not in d and len(d) >= 40:
            return
        days = d.setdefault(k, {})
        days[day] = days.get(day, 0) + 1
        for pk in list(d):
            for dk in [dk for dk in d[pk] if float(dk) < e.ts - 8 * 86400]:
                del d[pk][dk]
            if not d[pk]:
                del d[pk]
        while len(self.sender_paths) > self.SENDER_PATHS_MAX:
            self.sender_paths.pop(next(iter(self.sender_paths)))

    def most_held(self, now: float) -> list:
        """The names with the most copies held over the last 7 days, with how much they send, and any
        names that carried on another's repeat count, so one person behind several names shows as one."""
        cut = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)) - 6 * 86400
        rows = []
        linked = {a for v in self.name_links.values() for a in v.get("after", [])}
        for name, d in self.held_names.items():
            days = {k: v for k, v in d.items() if float(k) >= cut}
            held = sum(v[1] for v in days.values())
            if not held and name not in self.name_links and name not in linked:
                continue
            active = sum(1 for v in days.values() if v[0])
            today = d.get(str(int(time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)))), [0, 0])
            rows.append({"name": name, "held": held, "messages": sum(v[0] for v in days.values()),
                         "days": active, "per_day": round(sum(v[0] for v in days.values()) / max(1, active)),
                         "today": today[1]})
        # group linked names: a name that carried on from others takes their rows
        by = {r["name"]: r for r in rows}
        for name, link in self.name_links.items():
            if link.get("ts", 0) < now - 7 * 86400:
                continue
            head = by.get(name)
            for a in link.get("after", []):
                r = by.pop(a, None) if a != name else None
                if r is None:
                    continue
                if head is None:
                    head = by[name] = {"name": name, "held": 0, "messages": 0, "days": 0, "per_day": 0, "today": 0}
                for f in ("held", "messages", "today"):
                    head[f] += r[f]
                head["days"] = max(head["days"], r["days"])
                head.setdefault("also", []).append(a)
                head["also"].extend(r.get("also", []))
            if head is not None and head.get("also"):
                head["per_day"] = round(head["messages"] / max(1, head["days"]))
        return sorted((r for r in by.values() if r["held"]), key=lambda r: (-r["held"], -r["today"]))[:8]

    def _people_block(self, b: Optional[dict]) -> bool:
        return bool(b) and b["kind"] in PEOPLE_KINDS

    def _count(self, e: Event):
        # The same counts again per channel, so the Overview graphs can show one channel at a time.
        hour = str(int(e.ts // 3600 * 3600))
        f = ("m", "c", "x", "g")
        b0 = self.hist.get(hour) or {}
        before = [b0.get(k, 0) for k in f]
        self._count_all(e)
        h = self.hist.get(hour)
        if not h or not e.channel:
            return
        d = [h.get(k, 0) - n for k, n in zip(f, before)]
        if not any(d):
            return
        chs = h.setdefault("ch", {})
        if e.channel not in chs and len(chs) >= 20:
            return
        c = chs.setdefault(e.channel, {})
        for k, n in zip(f, d):
            if n:
                c[k] = c.get(k, 0) + n

    def _count_all(self, e: Event):
        if e.ts <= self.hist_mark:
            return  # already counted before a restart
        self.hist_mark = e.ts
        hour = str(int(e.ts // 3600 * 3600))
        h = self.hist.setdefault(hour, {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "h": {}})
        h["m"] += 1
        hn = self._held_day(e)
        if hn is not None:
            hn[0] += 1
        if e.matched and hn is not None and e.path:
            # count this copy as held first, so the copy that makes a name a repeat spammer is placed too
            hn[1] += 1
            self._note_sender_path(e)
            hn[1] -= 1
        else:
            self._note_sender_path(e)
        b = self.blocks.get(e.matched) if e.matched else None
        cc = self.clusters.get(e.campaign) if e.campaign is not None else None
        spammy = e.random or e.obfuscated or bool(cc and cc.get("strong"))
        v = self.verdict.get(e.packet) if e.packet else None
        protecting = self.cfg["mode"] == "protect" and not self.cfg.get("paused")
        if v is not None and protecting and e.matched and v[0] and self.rule_action(b or {}) == "drop":
            # SpamGuard had a block for it, but openHop passed a copy on anyway
            e.leaked = True
            if self._people_block(b) and not spammy:
                return  # a genuine-looking message that wasn't actually held
            h["x"] += 1
            if b and b.get("created", e.ts) + 15 < e.ts:  # the block was already in openHop: a real leak
                h["l"] = h.get("l", 0) + 1
            hop = e.first_hop
            h["h"][hop] = h["h"].get(hop, 0) + 1
            return
        if e.matched:
            if self._people_block(b) and not spammy:
                h["g"] += 1
                return
            h["c"] += 1
            if hn is not None:
                hn[1] += 1
            if self.cfg["mode"] == "protect" and not self.cfg.get("paused"):
                h["a"] = round(h["a"] + self.airtime_ms(e.length), 1)
        elif spammy and not self.is_known(e.sender):
            h["x"] += 1  # a known name with an odd-looking handle isn't spam
        else:
            return
        hop = e.first_hop
        h["h"][hop] = h["h"].get(hop, 0) + 1
        if e.path:  # whole routes, so the map can work out where the spam really entered the mesh
            ps = h.setdefault("p", {})
            k = ">".join(e.path)
            if k in ps or len(ps) < 100:
                ps[k] = ps.get(k, 0) + 1
                # who sent it, as a short code (never the name), so the map can count senders as well
                who = hashlib.sha1(e.sender.encode(), usedforsecurity=False).hexdigest()[:6]
                ss = h.setdefault("s", {}).setdefault(k, [])
                if who not in ss and len(ss) < 20:
                    ss.append(who)
        if len(self.hist) > 200:
            for k in sorted(self.hist)[:-192]:
                del self.hist[k]

    def metrics(self) -> dict:
        now = time.time()
        # Everything is kept, but after "Start again from scratch" the page counts from the reset hour on.
        shown_from = int(getattr(self, "reset_at", 0) // 3600 * 3600)
        hist = {k: v for k, v in self.hist.items() if int(k) >= shown_from} if shown_from else self.hist
        cut24, cut7 = now - 86400, now - 7 * 86400
        def tot(cut):
            t = {"m": 0, "c": 0, "x": 0, "g": 0, "a": 0.0, "l": 0, "fc": 0, "fx": 0, "fs": 0.0, "wh": 0, "ws": 0}
            for k, v in hist.items():
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
            v = hist.get(str(this_hour - i * 3600), {})
            hourly.append({"t": this_hour - i * 3600, "c": v.get("c", 0), "x": v.get("x", 0), "m": v.get("m", 0),
                           "fc": v.get("fc", 0), "fx": v.get("fx", 0), "bz": v.get("bz"),
                           "nf": v.get("nf"), "nfx": v.get("nfx"), "ie": bool(v.get("ie")),
                           "af": round(100 * v["af"] / v["ar"]) if v.get("ar") else None})
        daily = []
        for i in range(6, -1, -1):
            day0 = time.mktime(time.localtime(now)[:3] + (0, 0, 0, 0, 0, -1)) - i * 86400
            c = x = m = fc = fx = ar = sa = fs = 0
            bz = None
            for k, v in hist.items():
                if day0 <= int(k) < day0 + 86400:
                    c += v.get("c", 0)
                    x += v.get("x", 0)
                    m += v.get("m", 0)
                    fc += v.get("fc", 0)
                    fx += v.get("fx", 0)
                    ar += v.get("ar", 0)
                    sa += v.get("a", 0)
                    fs += v.get("fs", 0)
                    if v.get("bz") is not None:
                        bz = max(bz or 0, v["bz"])
            daily.append({"t": day0, "c": c, "x": x, "m": m, "fc": fc, "fx": fx, "bz": bz,
                          "ar": round(ar), "sa": round(sa), "fs": round(fs)})
        by_hour = [0] * 24  # spam by hour of day, last 7 days
        sources: dict[str, dict] = {}
        fsrc: dict[str, dict] = {}   # where FloodGuard's stopped flood packets came into the mesh
        for k, v in hist.items():
            t = int(k)
            if t < cut7:
                continue
            for hop, n in (v.get("fh") or {}).items():
                s7 = fsrc.setdefault(hop, {"hop": hop, "d7": 0, "d1": 0, "last": 0})
                s7["d7"] += n
                if t >= cut24 - 3600:
                    s7["d1"] += n
                s7["last"] = max(s7["last"], t)
        flood_sources = sorted(fsrc.values(), key=lambda s: (-s["d7"], -s["d1"]))[:10]
        for s7 in flood_sources:
            s7["candidates"] = self.repeaters_for(s7["hop"])
        for k, v in hist.items():
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
        # Per channel, for the Overview's channel picker. Only hours counted since v5.16 carry a split.
        ch_since = min((int(k) for k, v in hist.items() if "ch" in v), default=None)
        names = set((self.cfg.get("channels") or {}).keys())
        for k, v in hist.items():
            if int(k) >= cut7 - 3600:
                names |= set((v.get("ch") or {}).keys())
        per_ch = {}
        for name in sorted(names, key=lambda n: (n != "Public", n.lower())):
            def one(v, name=name):
                return (v.get("ch") or {}).get(name) or {}
            hr = []
            for r in hourly:
                c = one(hist.get(str(r["t"]), {}))
                hr.append({"t": r["t"], "c": c.get("c", 0), "x": c.get("x", 0), "m": c.get("m", 0)})
            dy = []
            for r in daily:
                c = x = m = 0
                for k, v in hist.items():
                    if r["t"] <= int(k) < r["t"] + 86400:
                        o = one(v)
                        c += o.get("c", 0)
                        x += o.get("x", 0)
                        m += o.get("m", 0)
                dy.append({"t": r["t"], "c": c, "x": x, "m": m})
            bh = [0] * 24
            t24 = {"m": 0, "c": 0, "x": 0}
            for k, v in hist.items():
                t = int(k)
                o = one(v)
                if t >= cut7:
                    bh[time.localtime(t).tm_hour] += o.get("c", 0) + o.get("x", 0)
                if t >= cut24 - 3600:
                    for f in t24:
                        t24[f] += o.get(f, 0)
            per_ch[name] = {"hourly": hr, "daily": dy, "by_hour": bh, "d1": t24}
        hidden = getattr(self, "hidden_sources", {}) or {}
        top = sorted((s7 for s7 in sources.values() if s7["last"] > hidden.get(s7["hop"], 0)),
                     key=lambda s: (-s["d7"], -s["d1"]))[:15]
        # Worked out on the background map thread (map_refresh); never computed here, under the lock.
        ent = (getattr(self, "_geo", None) or {}).get("ent") or {"entries": [], "unplaced": {"d1": 0, "d7": 0},
                                                                  "likely": {}, "working": True}
        entries = [e for e in ent["entries"]
                   if not any((e.get("last") or 0) <= hidden.get(c, 0) for c in e["codes"] + [e["code"]])]
        for e in entries:
            e["blocked"] = any(f"hop:{c}" in self.blocks for c in e["codes"] + [e["code"]])
        for s7 in top:
            s7["blocked"] = f"hop:{s7['hop']}" in self.blocks
            s7["allowed"] = self.hop_allowed(s7["hop"]) if s7["hop"] != "DIRECT" else False
            s7["candidates"] = self.repeaters_for(s7["hop"])
            s7["likely"] = ent["likely"].get(s7["hop"])
        return {"d1": tot(cut24), "d7": tot(cut7), "hourly": hourly, "daily": daily, "by_hour": by_hour,
                "sources": top, "flood_sources": flood_sources, "most_held": self.most_held(now),
                "entries": entries, "unplaced": ent["unplaced"],
                "senders": ent.get("senders") or [], "senders_unplaced": ent.get("senders_unplaced") or 0,
                "learned": ent.get("learned", 0), "advert_routes": ent.get("advert_routes", 0),
                "map_working": bool(ent.get("working")),
                "rulecheck_fix": self.openhop_rulecheck_fix(),
                "map_directory": bool(self.cfg.get("map_directory")), "public_repeaters": len(self.public_reps["list"]),
                "public_error": self.public_reps.get("error"),
                "me": self.me, "radio_known": bool(self.airtime_ms(40)),
                "since": min((int(k) for k in hist), default=None),
                "channels": per_ch, "channels_since": ch_since, "floodguard": self.fg_status(),
                "interference": self.jam_status(),
                "wardrive": {"enabled": bool(self.cfg.get("wardrive_block")), "channels": sorted(self.wardrive_channels()),
                             "checked_text": sorted(self.wardrive_collisions()),
                             "rules": sorted(self.wardrive_rule_ids()) if self.cfg.get("wardrive_block") else []}}

    LINK_KM = 130        # longest plausible single LoRa link between repeaters
    UNKNOWN_COST = 60    # cost of leaving a hop unplaced (no repeater with that code nearby)
    NEAR_KM = 30         # a repeater this close to a known one could be its neighbour by that code

    @staticmethod
    def parse_advert(payload: bytes) -> Optional[dict]:
        """MeshCore advert: public key (32), time (4), signature (64), then flags, and the location
        (two signed 32-bit millionths of a degree) when flag 0x10 is set, then the name."""
        if len(payload) < 101:
            return None
        key = payload[:32].hex().upper()
        flags = payload[100]
        node_type = flags & 0x0F
        lat = lon = None
        i = 101
        if flags & 0x10:
            if len(payload) < i + 8:
                return None
            lat, lon = struct.unpack_from("<ii", payload, i)
            lat, lon = lat / 1e6, lon / 1e6
            i += 8
        if flags & 0x20:
            i += 2
        if flags & 0x40:
            i += 2
        name = payload[i:].split(b"\0")[0].decode("utf-8", "replace")[:40] if flags & 0x80 else ""
        return {"key": key, "type": node_type, "lat": lat, "lon": lon, "name": name}

    def learn_advert(self, p: dict):
        """Remember the route a fixed node's advert (repeater or room server, with a location) took."""
        try:
            adv = self.parse_advert(bytes.fromhex(p.get("payload") or ""))
        except ValueError:
            return
        if adv and adv["type"] in (2, 3) and re.fullmatch(r"[0-9A-F]{64}", adv["key"] or ""):
            try:
                ts = float(p.get("timestamp") or time.time())
            except (TypeError, ValueError):
                ts = time.time()
            self.node_ids[adv["key"]] = max(self.node_ids.pop(adv["key"], 0.0), ts)
            while len(self.node_ids) > 5000:
                self.node_ids.popitem(last=False)
        if not adv or adv["type"] not in (2, 3) or adv["lat"] is None:
            return
        if not (adv["lat"] or adv["lon"]) or abs(adv["lat"]) > 90 or abs(adv["lon"]) > 180:
            return
        path = parse_path(p.get("original_path"))
        rk = adv["key"] + "|" + ">".join(path)
        seen = str(p.get("packet_hash") or p.get("id")) + "|" + rk
        if seen in self._adv_seen:
            return
        self._adv_seen[seen] = None
        while len(self._adv_seen) > 20000:
            self._adv_seen.popitem(last=False)
        ts = float(p.get("timestamp") or time.time())
        v = self.adv_routes.get(rk)
        if v:
            v[0] += 1
            v[1] = max(v[1], ts)
            v[2], v[3], v[4] = adv["lat"], adv["lon"], adv["name"]
        else:
            self.adv_routes[rk] = [1, ts, adv["lat"], adv["lon"], adv["name"]]
            self._adv_stamp += 1
            if len(self.adv_routes) > 15000:
                for k, _ in sorted(self.adv_routes.items(), key=lambda kv: kv[1][1])[:2000]:
                    del self.adv_routes[k]

    def _rep_index(self) -> dict:
        idx = getattr(self, "_rep_idx", None)
        stamp = (self.repeaters["ts"], self.public_reps["ts"] if self.cfg.get("map_directory") else 0)
        if idx is None or idx[0] != stamp:
            located = [r for r in self.repeaters["list"] if r.get("lat") is not None and r.get("lon") is not None]
            if self.cfg.get("map_directory"):
                have = {r["key"] for r in self.repeaters["list"]}
                located += [r for r in self.public_reps["list"] if r["key"] not in have]
            by: dict[str, list] = {}
            for r in located:
                for n in (2, 4, 6):
                    by.setdefault(r["key"][:n], []).append(r)
            for v in by.values():
                v.sort(key=lambda r: -r["seen"])
            idx = (stamp, located, {}, by)
            self._rep_idx = idx
        return idx

    def _cands(self, code: str) -> list:
        return self._rep_index()[3].get(code, [])

    @staticmethod
    def _km(a, b) -> float:
        la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 6371 * 2 * math.asin(min(1.0, math.sqrt(h)))

    def _fit_chain(self, path: list, fixed: Optional[dict] = None, anchor: Optional[tuple] = None):
        """Place each route code at a repeater so that every hop is within radio range of the next,
        walking back from this repeater. 'fixed' hops are already known; 'anchor' is where the
        message started (known for adverts), which stops the chain being squeezed towards us.
        Returns (cost, [(index, repeater), ...])."""
        me = (float(self.me["lat"]), float(self.me["lon"]))
        fixed = fixed or {}
        n = len(path)
        states = {("me", 0): (0.0, me, [])}
        for i in range(n - 1, -1, -1):
            if i in fixed:
                cs = [fixed[i]]
            else:
                cs = self._cands(path[i])[:40]
                if anchor:
                    cs = [r for r in cs if self._km(anchor, (r["lat"], r["lon"])) <= self.LINK_KM * (i + 1)
                          and self._km(me, (r["lat"], r["lon"])) <= self.LINK_KM * (n - i)]
            skip = self.UNKNOWN_COST * (3 if i in fixed else 1)
            nxt = {}
            for (sid, gap), (cost, pos, placed) in states.items():
                k2, c2 = (sid, gap + 1), cost + skip
                if k2 not in nxt or c2 < nxt[k2][0]:
                    nxt[k2] = (c2, pos, placed)
                for r in cs:
                    d = self._km(pos, (r["lat"], r["lon"]))
                    if d > self.LINK_KM * (gap + 1):
                        continue
                    k2, c2 = (r["key"], 0), cost + d
                    if k2 not in nxt or c2 < nxt[k2][0]:
                        nxt[k2] = (c2, (r["lat"], r["lon"]), placed + [(i, r)])
            states = dict(sorted(nxt.items(), key=lambda kv: kv[1][0])[:60])
        if anchor:
            best = None
            for (_sid, gap), (cost, pos, placed) in states.items():
                d = self._km(pos, anchor)
                if d > self.LINK_KM * (gap + 1):
                    continue
                if best is None or cost + d < best[0]:
                    best = (cost + d, placed)
            return best or (float("inf"), [])
        cost, _, placed = min(states.values(), key=lambda v: v[0])
        return cost, placed

    def _learned(self) -> dict:
        """(route code, the code after it, or 'ME') -> the repeater it is, learnt from advert routes.
        Built in the background by learn_step(); this only hands back the latest table."""
        return getattr(self, "_learned_table", {})

    def learn_step(self, work_s: float = 0.3, rest_s: float = 0.3, until: float = 0.0) -> bool:
        """Fit advert routes not yet fitted (or last fitted on an earlier day), a little at a time,
        resting between batches so polling and the web page never wait; then rebuild the table.
        Each advert route is fitted anchored at the advert's own location (so the chain can't be
        squeezed towards us) and votes for the repeater at each hop; the advert's own repeater votes
        twice for its code next to the first hop. A code counts as learnt in a context only when one
        repeater has at least 3 votes and 80% of them. Tested on a week of real adverts: a code learnt
        this way matched the repeater the advert itself named 87% of the time.
        Runs on the background map thread, never under self.lock. Returns True if anything changed."""
        me = self.me or {}
        if me.get("lat") is None or me.get("lon") is None:
            return False
        fits = self.__dict__.setdefault("_adv_fits", {})      # route -> (day fitted, votes)
        day = int(time.time() // 86400)
        with self.lock:
            routes = dict(self.adv_routes)
        pending = [rk for rk in routes if rk not in fits] + [rk for rk in routes if rk in fits and fits[rk][0] != day]
        t0 = time.time()
        done = 0
        for rk in pending:
            cnt, last, lat, lon, name = routes[rk]
            path = rk.partition("|")[2]
            path = path.split(">") if path else []
            out = []
            if path and len(path) <= 24:
                _, placed = self._fit_chain(path, anchor=(lat, lon))
                out = [((path[i], path[i + 1] if i + 1 < len(path) else "ME"),
                        {"key": r["key"], "name": r.get("name") or "", "lat": r["lat"], "lon": r["lon"]}) for i, r in placed]
            fits[rk] = (day, out)
            done += 1
            if time.time() - t0 > work_s:
                if until and time.time() > until:
                    break
                time.sleep(rest_s)
                t0 = time.time()
        for rk in [rk for rk in fits if rk not in routes]:
            del fits[rk]
        built = getattr(self, "_learned_built", 0.0)
        if not done and time.time() - built < 300 and getattr(self, "_learned_stamp", None) == self._adv_stamp:
            return False
        votes: dict[tuple, collections.Counter] = {}
        reps: dict[str, dict] = {}
        horizon = time.time() - 14 * 86400
        for rk, (cnt, last, lat, lon, name) in routes.items():
            if last < horizon:
                continue
            key, _, ps = rk.partition("|")
            path = ps.split(">") if ps else []
            reps[key] = {"key": key, "name": name, "lat": lat, "lon": lon}
            code = key[:len(path[0])] if path else key[:2]
            votes.setdefault((code, path[0] if path else "ME"), collections.Counter())[key] += 2 * cnt
            for ctx, r in fits.get(rk, (0, []))[1]:
                reps.setdefault(r["key"], r)
                votes.setdefault(ctx, collections.Counter())[r["key"]] += cnt
        learned = {}
        for ctx, c in votes.items():
            (k, top), total = c.most_common(1)[0], sum(c.values())
            if top >= 3 and top >= 0.8 * total:
                learned[ctx] = reps[k]
        self._learned_table = learned
        self._learned_built = time.time()
        self._learned_stamp = self._adv_stamp
        return True

    def map_refresh(self, rest_s: float = 0.3):
        """Learn from new adverts, then work out the spam entry points for the map. Both are slow on a
        Pi, so they run here, on the background map thread, outside self.lock; the web page shows the
        latest result (self._geo) instead of computing it on every request."""
        changed = self.learn_step(rest_s=rest_s)
        geo = self.__dict__.setdefault("_geo", {"ts": 0.0, "ent": None})
        if not changed and geo["ent"] is not None and time.time() - geo["ts"] < 60:
            return
        now = time.time()
        with self.lock:
            hist = {k: {"p": dict(v.get("p") or {}), "s": {pk: list(pv) for pk, pv in (v.get("s") or {}).items()}}
                    for k, v in self.hist.items()}
            spammers = {n: {pk: dict(pv) for pk, pv in d.items()} for n, d in self.sender_paths.items()
                        if self.repeat_spammer(n, now)}
            links = {n: list(v.get("after", [])) for n, v in self.name_links.items() if v.get("ts", 0) >= now - 7 * 86400}
        cut24, cut7 = now - 86400, now - 7 * 86400
        geo["ent"] = self.spam_entries(cut24, cut7, hist, spammers, links)
        geo["ts"] = time.time()

    def map_loop(self, stop: threading.Event):
        while not stop.is_set():
            try:
                self.map_refresh()
            except Exception as e:
                log.debug("map refresh failed: %s", e)
            stop.wait(5)

    def resolve_path(self, path: list, distrust: frozenset = frozenset()) -> Optional[dict]:
        """Work out where a message entered the mesh. Route codes are short and shared by many
        repeaters, so a code on its own could be anywhere in the country. Codes are looked up in what
        repeater adverts have taught us, in the context of the next code along:
        - kind 'id': the first code is a repeater we've learnt, and it's in radio range of the next
          hop (a repeater can advertise any location, so a claimed location far from its real
          neighbours isn't believed);
        - kind 'next': the first repeater isn't known but the one it handed the message to is, so the
          message entered one hop from there ('claims' names an advert that gave a far-off location);
        - kind 'guess': neither is known; the hops are fitted so each is in radio range of the next.
        """
        me = self.me or {}
        if me.get("lat") is None or me.get("lon") is None or not path:
            return None
        cache = self._rep_index()[2]
        learned = self._learned()
        stamp = id(learned)
        key = (">".join(path), distrust)
        if key in cache and cache[key][0] == stamp:
            return cache[key][1]
        def ctx(i):
            return (path[i], path[i + 1] if i + 1 < len(path) else "ME")
        x = learned.get(ctx(0))
        y = learned.get(ctx(1)) if len(path) > 1 else None
        res = None
        far = bool(x and y and self._km((x["lat"], x["lon"]), (y["lat"], y["lon"])) > 2 * self.NEAR_KM)
        if x and not far and x["key"] not in distrust:
            res = {"kind": "id", "key": x["key"], "name": x.get("name") or "", "lat": x["lat"], "lon": x["lon"],
                   "index": 0, "code": path[0], "sure": True, "checked": bool(y)}
        elif y:
            res = {"kind": "next", "key": y["key"], "name": y.get("name") or "", "lat": y["lat"], "lon": y["lon"],
                   "index": 0, "code": path[0], "sure": True, "claims": (x.get("name") or "") if x else ""}
        else:
            fixed = {i: learned[ctx(i)] for i in range(len(path)) if ctx(i) in learned}
            if x and 0 in fixed:
                del fixed[0]                     # don't believe a location its neighbours contradict
            _, placed = self._fit_chain(path, fixed=fixed)
            placed = [(i, r) for i, r in placed if not (x and r["key"] == x["key"])]
            if placed:
                i, r = min(placed, key=lambda t: t[0])
                res = {"kind": "guess", "key": r["key"], "name": r.get("name") or "", "lat": r["lat"], "lon": r["lon"],
                       "index": i, "code": path[i], "sure": False}
        if res is not None and x and res["kind"] != "id":
            res["claims"] = x.get("name") or ""
        if res is not None:
            res["far"] = far
            res["x_key"] = x["key"] if x else None
            res["y"] = (y["lat"], y["lon"], y["key"]) if y else None
        if len(cache) > 5000:
            cache.clear()
        cache[key] = (stamp, res)
        return res

    def _area_groups(self, pts: list) -> list:
        """Group (lat, lon, weight, ...) points by area: each joins the first group whose centre is
        within AREA_KM, heaviest first."""
        groups: list[list] = []
        for p in sorted(pts, key=lambda p: -p[2]):
            for g in groups:
                if self._km(self._geomedian(g), p) <= self.AREA_KM:
                    g.append(p)
                    break
            else:
                groups.append([p])
        return groups

    @staticmethod
    def _geomedian(pts: list) -> tuple:
        """Weighted geometric median of (lat, lon, weight): the point closest to all of them."""
        w = sum(p[2] for p in pts)
        c = (sum(p[0] * p[2] for p in pts) / w, sum(p[1] * p[2] for p in pts) / w)
        for _ in range(50):
            sx = sy = sw = 0.0
            for p in pts:
                d = max(0.5, SpamGuard._km(c, p))
                sx += p[0] * p[2] / d
                sy += p[1] * p[2] / d
                sw += p[2] / d
            c = (sx / sw, sy / sw)
        return c

    ID_AREA_KM = 45      # a learnt first repeater further than this from where its code's spam is handed on isn't believed
    AREA_KM = 40         # neighbours of one source further apart than this are treated as separate sources
    SURE_SPREAD_KM = 35  # an area is sure when 2+ known neighbours sit within this of its centre

    def spam_entries(self, cut24: float, cut7: float, hist: Optional[dict] = None,
                     spammers: Optional[dict] = None, links: Optional[dict] = None) -> dict:
        """Where spam entered the mesh over the last 7 days.
        Learnt repeaters are entries of their own. Spam whose first repeater is unknown (often the
        spammer's own node, never advertised) is placed from the known repeaters it was handed to:
        for each first code those are grouped by area, and each group's centre is where it entered.
        A group is 'sure' when at least two different known repeaters agree (median distance from
        the centre within SURE_SPREAD_KM). In a test on real adverts with the first repeater hidden,
        sure groups were within 30 km of the true spot 91% of the time. 'exact' counts sure messages."""
        if hist is None:
            hist = self.hist
        entries: dict[str, dict] = {}
        unplaced = {"d1": 0, "d7": 0}
        by_code: dict[str, collections.Counter] = {}
        nexts: dict[str, dict] = {}     # first code -> neighbour key -> [lat, lon, d7, d1, last, name, claims]

        # Check each learnt first repeater against everything else its code's spam tells us. A repeater
        # can advertise any location, and a short code can belong to a real repeater elsewhere as well as
        # to the spammer's unlisted one. So for each first code, the known repeaters its spam is handed
        # to are grouped by area; when the main group is sure (2+ different repeaters agreeing), a
        # learnt repeater for that code more than ID_AREA_KM from its centre isn't believed. Failing
        # that, one whose spam is mostly handed to repeaters out of its range isn't believed either.
        check: dict[str, list] = {}
        ys: dict[str, dict] = {}
        xs: dict[str, set] = {}
        for k, v in hist.items():
            if int(k) < cut7:
                continue
            for ps, n in (v.get("p") or {}).items():
                r = self.resolve_path(ps.split(">"))
                if not r:
                    continue
                code = ps.split(">")[0]
                if r.get("x_key"):
                    xs.setdefault(code, set()).add(r["x_key"])
                if r.get("y"):
                    yl = ys.setdefault(code, {}).setdefault(r["y"][2], [r["y"][0], r["y"][1], 0])
                    yl[2] += n
                if r.get("far"):
                    check.setdefault(r["x_key"], [0, 0])[1] += n
                elif r["kind"] == "id" and r.get("checked"):
                    check.setdefault(r["key"], [0, 0])[0] += n
        distrust = set(k for k, (ok, bad) in check.items() if bad > ok)
        reps_by_key = {r["key"]: r for r in self._learned().values()}
        for code, pts in ys.items():
            groups = self._area_groups([(p[0], p[1], p[2], kk) for kk, p in pts.items()])
            if not groups:
                continue
            main = max(groups, key=lambda g: sum(p[2] for p in g))
            c = self._geomedian(main)
            ds = sorted(self._km(c, p) for p in main)
            if len(main) < 2 or ds[len(ds) // 2] > self.SURE_SPREAD_KM:
                continue
            for xk in xs.get(code, ()):
                x = reps_by_key.get(xk)
                if x and self._km(c, (x["lat"], x["lon"])) > self.ID_AREA_KM:
                    distrust.add(xk)
        distrust = frozenset(distrust)

        def entry(k, r, sure):
            return entries.setdefault(k, {"key": k, "name": r["name"], "lat": r["lat"], "lon": r["lon"], "code": r["code"],
                                          "d1": 0, "d7": 0, "exact": 0, "before": collections.Counter(), "codes": collections.Counter(),
                                          "last": 0, "kind": r.get("kind", "guess"), "near": [], "claims": [], "spread_km": None,
                                          "_s7": set(), "_s1": set()})
        counted_senders = False

        for k, v in hist.items():
            t = int(k)
            if t < cut7:
                continue
            recent = t >= cut24 - 3600
            for ps, n in (v.get("p") or {}).items():
                path = ps.split(">")
                whos = set((v.get("s") or {}).get(ps) or [])
                counted_senders = counted_senders or bool(whos)
                r = self.resolve_path(path, distrust)
                if not r:
                    unplaced["d7"] += n
                    if recent:
                        unplaced["d1"] += n
                    continue
                if r["kind"] == "next":
                    nb = nexts.setdefault(path[0], {}).setdefault(r["key"], [r["lat"], r["lon"], 0, 0, 0, r["name"], collections.Counter(),
                                                                           set(), set()])
                    nb[2] += n
                    nb[3] += n if recent else 0
                    nb[4] = max(nb[4], t)
                    nb[7] |= whos
                    if recent:
                        nb[8] |= whos
                    if r.get("claims"):
                        nb[6][r["claims"]] += n
                    continue
                e = entry(r["key"], r, r["sure"])
                e["d7"] += n
                e["_s7"] |= whos
                if recent:
                    e["d1"] += n
                    e["_s1"] |= whos
                if r["sure"]:
                    e["exact"] += n
                if r["index"]:
                    e["before"][r["index"]] += n
                e["codes"][path[0]] += n
                e["last"] = max(e["last"], t)
                by_code.setdefault(path[0], collections.Counter())[r["key"]] += n
        for code, nbs in nexts.items():
            groups: list[list] = []
            for nk, nb in sorted(nbs.items(), key=lambda kv: -kv[1][2]):
                for g in groups:
                    c = self._geomedian([(p[1][0], p[1][1], p[1][2]) for p in g])
                    if self._km(c, (nb[0], nb[1])) <= self.AREA_KM:
                        g.append((nk, nb))
                        break
                else:
                    groups.append([(nk, nb)])
            for gi, g in enumerate(groups):
                c = self._geomedian([(p[1][0], p[1][1], p[1][2]) for p in g])
                ds = sorted(self._km(c, (p[1][0], p[1][1])) for p in g)
                spread = ds[len(ds) // 2]
                sure = len(g) >= 2 and spread <= self.SURE_SPREAD_KM
                k = f"area:{code}:{gi}"
                d7, d1 = sum(p[1][2] for p in g), sum(p[1][3] for p in g)
                claims = collections.Counter()
                for p in g:
                    claims.update(p[1][6])
                entries[k] = {"key": k, "name": "", "lat": c[0], "lon": c[1], "code": code, "d1": d1, "d7": d7,
                              "_s7": set().union(*[p[1][7] for p in g]), "_s1": set().union(*[p[1][8] for p in g]),
                              "exact": d7 if sure else 0, "before": collections.Counter(), "codes": collections.Counter({code: d7}),
                              "last": max(p[1][4] for p in g), "kind": "area",
                              "near": [p[1][5] for p in sorted(g, key=lambda p: -p[1][2])[:4]],
                              "claims": [n for n, _ in claims.most_common(2)], "spread_km": round(spread)}
                by_code.setdefault(code, collections.Counter())[k] += d7
        out = []
        for e in sorted(entries.values(), key=lambda e: -e["d7"])[:25]:
            s7, s1 = e.pop("_s7", set()), e.pop("_s1", set())
            # senders are only counted from this version on; older hours only have message counts
            e["s7"], e["s1"] = (len(s7), len(s1)) if counted_senders else (None, None)
            e["codes"] = [c for c, _ in e["codes"].most_common(8)]
            e["blocked"] = any(f"hop:{c}" in self.blocks for c in e["codes"] + [e["code"]])
            e["typical_before"] = e["before"].most_common(1)[0][0] if e["before"] else 0
            del e["before"]
            e["shared"] = self.code_share(e["code"], e["key"])
            out.append(e)
        names = {e["key"]: e for e in out}
        likely = {}
        for code, cnt in by_code.items():
            k, n = cnt.most_common(1)[0]
            if k in names:
                e = names[k]
                likely[code] = {"name": e["name"] or (e["near"][0] if e["near"] else ""), "key": k,
                                "exact": e["kind"] == "id" and e["code"] == code}
        senders, senders_unplaced = self.spam_senders(spammers or {}, links or {}, cut24, cut7, distrust)
        return {"entries": out, "unplaced": unplaced, "likely": likely, "senders": senders,
                "senders_unplaced": senders_unplaced,
                "learned": len(self._learned()), "advert_routes": len(self.adv_routes)}

    SENDER_MIN_MESSAGES = 3     # a repeat spammer heard fewer times than this in 7 days isn't placed

    # ---- the quarantine: every channel message in one list, with what SpamGuard did and why ----
    Q_REASON = {"repeat": "The same message again and again from this name",
                "slowrepeat": "The same message many times today from this name",
                "replay": "An old message sent again by another device",
                "dedupe": "A copy of a message already sent under another name",
                "campaign": "The same message sent under several names",
                "hop": "Came through a repeater sending a burst of made-up names",
                "suffix": "Came the same way as a repeater sending spam",
                "route": "Started on a route you blocked",
                "rotation": "Came from a repeater that keeps changing its identity",
                "links": "A link from a name SpamGuard doesn't know, during spam",
                "lockdown": "Sent during a short lockdown for a big flood",
                "manual": "Matches a block you added"}
    Q_STATUSES = ("stopped", "held", "letthrough", "genuine")

    def _q_classify(self, m: dict) -> tuple:
        """(status, reason) for one message: stopped (spam SpamGuard held back), held (possibly genuine,
        caught up in a block meant for spam), letthrough (looked like spam but went out), or genuine."""
        src, kind = m.get("caught_source"), m.get("caught_kind")
        spammy = bool(m.get("random") or m.get("obfuscated") or (m.get("campaign_senders") or 0) >= 2)
        if m.get("caught_by"):
            people = kind in PEOPLE_KINDS
            if people and not spammy:
                return "held", self.Q_REASON.get(kind) or self.Q_REASON.get(src) or "Held by a block meant for spam"
            return "stopped", self.Q_REASON.get(src) or self.Q_REASON.get(kind) or "Matched a spam block"
        if spammy and not m.get("known"):
            why = ("Hidden or look-alike characters in the name" if m.get("obfuscated")
                   else "The same message as other names" if (m.get("campaign_senders") or 0) >= 2
                   else "A made-up looking name")
            return "letthrough", why + ", but nothing had repeated yet"
        return "genuine", "Passed on as normal"

    def _q_rows(self, days: int) -> tuple:
        """The messages of the last `days` days, newest last: from the evidence log when it is on (kept
        parsed per day file until the file changes), otherwise what is still in memory."""
        cut = time.time() - days * 86400
        if self.evidence is None:
            rows = []
            with self.lock:
                for e in list(self.events):
                    if e.ts < cut or not e.text:
                        continue
                    b = self.blocks.get(e.matched) if e.matched else None
                    cc = self.clusters.get(e.campaign) if e.campaign is not None else None
                    rows.append({"ts": e.ts, "packet": e.packet, "sender": e.sender, "text": e.text, "path": list(e.path),
                                 "channel": e.channel, "random": e.random, "obfuscated": e.obfuscated,
                                 "known": self.is_known(e.sender), "campaign_senders": len(cc["senders"]) if cc else 0,
                                 "caught_by": e.matched, "caught_kind": b["kind"] if b else None,
                                 "caught_source": b.get("source") if b else None, "own": self.is_own(e)})
            return rows, "memory"
        self.evidence.flush(force=True)
        cache = self.__dict__.setdefault("_q_cache", {})
        first = time.strftime("%Y-%m-%d", time.localtime(cut))
        keep = ("ts", "packet", "sender", "text", "path", "channel", "random", "obfuscated", "known", "campaign_senders",
                "caught_by", "caught_kind", "caught_source", "own")
        rows = []
        files = [f for f in self.evidence.files() if os.path.basename(f)[:10] >= first]
        for f in files:
            try:
                stt = os.stat(f)
            except OSError:
                continue
            got = cache.get(f)
            if not got or got[0] != (stt.st_mtime, stt.st_size):
                parsed = []
                try:
                    with open(f, encoding="utf-8") as fh:
                        for ln in fh:
                            if '"type": "msg"' not in ln:
                                continue
                            try:
                                m = json.loads(ln)
                            except ValueError:
                                continue
                            parsed.append({k: m.get(k) for k in keep})
                except OSError:
                    continue
                got = cache[f] = ((stt.st_mtime, stt.st_size), parsed)
            rows.extend(r for r in got[1] if (r.get("ts") or 0) >= cut)
        for f in [f for f in cache if f not in files]:
            del cache[f]
        return rows, "evidence"

    def quarantine(self, body: dict) -> dict:
        """One list of channel messages, like a mail quarantine. Filters: status, words, route codes (where
        it entered the mesh), names (a repeat spammer), 1 or 7 days, and copies of one message grouped."""
        status = body.get("status") or "all"
        if status not in ("all",) + self.Q_STATUSES:
            raise ValueError("Unknown filter")
        days = 7 if int(body.get("days") or 1) >= 7 else 1
        q = str(body.get("q") or "").strip().lower()[:80]
        codes = {str(c).upper() for c in (body.get("codes") or []) if c}
        names = {str(n) for n in (body.get("names") or []) if n}
        grouped = bool(body.get("group", True))
        limit = max(20, min(500, int(body.get("limit") or 100)))
        raw, source = self._q_rows(days)
        counts = {k: 0 for k in self.Q_STATUSES}
        picked = []
        # copies of a message one name kept repeating that went out before the limit was reached
        repeated = {(m.get("sender"), normalise(str(m.get("text") or ""))) for m in raw
                    if m.get("caught_source") in ("repeat", "slowrepeat", "replay")}
        for m in raw:
            if m.get("own") or not m.get("text"):
                continue
            path = m.get("path") or []
            if names and m.get("sender") not in names:
                continue
            st, why = self._q_classify(m)
            if st == "genuine" and (m.get("sender"), normalise(str(m.get("text") or ""))) in repeated:
                st, why = "letthrough", "An earlier copy of a message this name kept repeating"
            if codes and not (path and str(path[0]).upper() in codes and (st != "genuine" or names)):
                continue
            if q and q not in (str(m.get("sender")) + " " + str(m.get("text"))).lower():
                continue
            counts[st] += 1
            if status != "all" and st != status:
                continue
            picked.append((m, st, why))
        picked.sort(key=lambda t: -(t[0].get("ts") or 0))
        rows, index = [], {}
        for m, st, why in picked:
            text = str(m.get("text") or "")
            key = (st, m.get("channel"), normalise(text)[:120]) if grouped else id(m)
            if key in index:
                r = index[key]
                r["copies"] += 1
                if m.get("sender") not in r["_names"]:
                    r["_names"].add(m.get("sender"))
                continue
            if len(rows) >= limit:
                continue
            path = m.get("path") or []
            r = index[key] = {"ts": m.get("ts"), "sender": m.get("sender"), "text": text[:300], "channel": m.get("channel"),
                              "path": ">".join(path) or "direct", "first_hop": path[0] if path else None,
                              "status": st, "why": why, "matched": m.get("caught_by"), "packet": m.get("packet"),
                              "copies": 1, "_names": {m.get("sender")},
                              "known": bool(m.get("known")), "spammer": self.repeat_spammer(m.get("sender") or ""),
                              "label": self.labels.get(str(m.get("packet") or "")) or self.labels.get(f"{m.get('sender')}|{text}")}
            rows.append(r)
        for r in rows:
            r["senders"] = len(r.pop("_names"))
        return {"source": source, "days": days, "counts": counts, "total": sum(counts.values()),
                "shown": len(picked), "rows": rows, "mode": "paused" if self.cfg.get("paused") else self.cfg["mode"]}

    def messages_for(self, body: dict) -> dict:
        """The spam behind a point on the map (route codes), or everything from a repeat spammer (names)."""
        if not body.get("codes") and not body.get("names"):
            raise ValueError("Which repeater or sender?")
        r = self.quarantine({"codes": body.get("codes"), "names": body.get("names"), "days": 7, "group": False,
                             "limit": 150})
        return {"source": r["source"], "total": r["shown"],
                "messages": [{"ts": x["ts"], "sender": x["sender"], "text": x["text"][:200], "path": x["path"],
                              "channel": x["channel"], "caught": x["status"] == "stopped"} for x in r["rows"]]}

    def spam_senders(self, spammers: dict, links: dict, cut24: float, cut7: float,
                     distrust: frozenset = frozenset()) -> tuple:
        """Where each repeat spammer is heard from. Names that carried on each other's repeat count are one
        sender. Every message they sent counts here (not only the copies held), because it is where they
        are that matters, not what they said. A sender heard first by several repeaters is shown as one
        area: the middle of those repeaters, with a radius reaching most of them. They are probably
        somewhere all of them can hear."""
        parent: dict[str, str] = {}

        def root(n):
            while parent.get(n, n) != n:
                n = parent[n]
            return n
        for n, after in links.items():
            for a in after:
                if a in spammers or n in spammers:
                    parent[root(a)] = root(n)
        groups: dict[str, list] = {}
        for n in spammers:
            groups.setdefault(root(n), []).append(n)
        out, unplaced = [], 0
        for head, names in groups.items():
            pts: dict[str, list] = {}
            n7 = n1 = 0
            for name in names:
                for pk, days in spammers[name].items():
                    c7 = sum(v for k, v in days.items() if float(k) >= cut7 - 86400)
                    c1 = sum(v for k, v in days.items() if float(k) >= cut24 - 86400)
                    if not c7:
                        continue
                    n7 += c7
                    n1 += c1
                    r = self.resolve_path(pk.split(">"), distrust)
                    if not r or not r.get("sure"):
                        continue
                    p = pts.setdefault(r["key"], [r["lat"], r["lon"], 0, r["name"] or "", r["code"], r["kind"]])
                    p[2] += c7
            if n7 < self.SENDER_MIN_MESSAGES:
                continue
            if not pts:
                unplaced += 1
                continue
            ps = sorted(pts.values(), key=lambda p: -p[2])
            c = self._geomedian([(p[0], p[1], p[2]) for p in ps]) if len(ps) > 1 else (ps[0][0], ps[0][1])
            # reach most of the repeaters, weighted by how often each heard them first
            ds = sorted((self._km(c, (p[0], p[1])), p[2]) for p in ps)
            acc, need, radius = 0, 0.8 * sum(w for _, w in ds), 0.0
            for d, w in ds:
                acc += w
                radius = d
                if acc >= need:
                    break
            names_sorted = sorted(names, key=lambda x: -sum(sum(d.values()) for d in spammers[x].values()))
            out.append({"key": "sender:" + hashlib.sha1(head.encode(), usedforsecurity=False).hexdigest()[:8],
                        "names": names_sorted[:5], "lat": c[0], "lon": c[1],
                        "radius_km": round(min(max(radius, 3.0), self.AREA_KM), 1), "d7": n7, "d1": n1,
                        "repeaters": [{"name": p[3], "code": p[4], "n": p[2], "lat": p[0], "lon": p[1],
                                       "kind": p[5]} for p in ps[:6]],
                        "spread": len(ps) > 1 and ds[-1][0] > 2 * self.AREA_KM})
        out.sort(key=lambda x: -x["d7"])
        return out[:12], unplaced

    def code_share(self, code: str, key: Optional[str] = None, now: Optional[float] = None) -> dict:
        """Other repeaters heard here (in adverts, or in openHop's list) whose ID starts with this route
        code, and how many of them have no location, so the map can say when a pin could be one of
        several. Only repeaters this one has heard count: a short code is shared by many repeaters
        across the country, but only those in radio range could have carried the spam. Works offline."""
        if not code or code == "DIRECT":
            return {"others": 0, "unlocated": 0}
        now = time.time() if now is None else now
        code = code.upper()
        heard = {k for k, t in list(self.node_ids.items()) if t > now - self.NODE_ID_WINDOW and k.startswith(code)}
        heard |= {str(r.get("key") or "") for r in list(self.repeaters.get("list") or [])
                  if str(r.get("key") or "").startswith(code)}
        heard.discard("")
        if key:
            heard.discard(key)
        located = {r["key"] for r in self._cands(code)}
        return {"others": len(heard), "unlocated": len(heard - located)}

    def repeaters_for(self, hop: str) -> list:
        """Repeaters openHop has heard adverts from whose key starts with this route code.
        Short codes are shared by many repeaters, so this can be several."""
        if not hop or hop == "DIRECT":
            return []
        out = [r for r in self.repeaters["list"] if r["key"].startswith(hop)]
        return sorted(out, key=lambda r: -r["seen"])[:6]

    def _public_reps_path(self) -> str:
        st = self.cfg.get("state_file") or self.file_cfg.get("state_file", DEFAULT_CONFIG["state_file"])
        return os.path.join(os.path.dirname(st), "public-repeaters.json")

    def _load_public_reps(self):
        try:
            with open(self._public_reps_path()) as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("list"), list):
                self.public_reps = {"ts": float(d.get("ts") or 0), "list": d["list"], "error": None}
        except Exception:
            pass

    @staticmethod
    def _iso_ts(v) -> float:
        """Seconds since 1970 from the map's ISO dates, or 0 if missing or nonsense (nodes with no clock send 1970)."""
        if isinstance(v, (int, float)):
            t = float(v) / (1000 if v > 1e11 else 1)
        elif isinstance(v, str):
            try:
                t = float(calendar.timegm(time.strptime(v[:19], "%Y-%m-%dT%H:%M:%S")))
            except (ValueError, OverflowError):
                return 0.0
        else:
            return 0.0
        return t if 1577836800 <= t <= time.time() + 86400 else 0.0   # 2020 .. tomorrow

    @staticmethod
    def _same_radio(params, radio: Optional[dict]) -> bool:
        """False only when both sides say which radio settings they use and they can't hear each other."""
        if not isinstance(params, dict) or not radio:
            return True
        def num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None
        mf, nf = num(radio.get("frequency")), num(params.get("freq"))
        mb, nb = num(radio.get("bandwidth")), num(params.get("bw"))
        ms, ns = num(radio.get("spreading_factor")), num(params.get("sf"))
        if mf and mf > 1e5:
            mf /= 1e6                     # Hz -> MHz
        if mb and mb > 1000:
            mb /= 1000                    # Hz -> kHz
        if mf and nf and abs(mf - nf) > 0.05:
            return False
        if mb and nb and abs(mb - nb) > 0.5:
            return False
        if ms and ns and ms != ns:
            return False
        return True

    @staticmethod
    def parse_public_map(nodes, me: Optional[dict] = None, radius_km: float = 600,
                         radio: Optional[dict] = None, max_age_days: float = 90) -> list:
        """Repeaters (type 2) with a location from the public MeshCore map's node list: near us, on our
        radio settings and heard from in the last few months. One odd entry never spoils the rest."""
        if isinstance(nodes, dict):
            nodes = nodes.get("nodes") or nodes.get("data") or []
        out = []
        here = (float(me["lat"]), float(me["lon"])) if me and me.get("lat") is not None and me.get("lon") is not None else None
        oldest = time.time() - max_age_days * 86400
        for n in nodes if isinstance(nodes, list) else []:
            try:
                if not isinstance(n, dict) or str(n.get("type")) != "2":
                    continue
                key = str(n.get("public_key") or "").upper()
                lat, lon = n.get("lat", n.get("adv_lat")), n.get("lon", n.get("adv_lon"))
                if not re.fullmatch(r"[0-9A-F]{8,64}", key) or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    continue
                if not (lat or lon) or abs(lat) > 90 or abs(lon) > 180:
                    continue
                if here and SpamGuard._km(here, (lat, lon)) > radius_km:
                    continue
                if not SpamGuard._same_radio(n.get("params"), radio):
                    continue
                seen = SpamGuard._iso_ts(n.get("last_advert")) or SpamGuard._iso_ts(n.get("updated_date"))
                if seen and seen < oldest:
                    continue
                out.append({"key": key, "name": str(n.get("adv_name") or "")[:40], "lat": float(lat), "lon": float(lon),
                            "seen": seen, "src": "map"})
            except Exception:
                continue
        return out

    # ---- what each protection level would have done, replayed from the evidence log
    PREVIEW_EVERY = 86400          # once a day
    PREVIEW_SPAN = 2 * 86400       # over the last two days
    PREVIEW_MIN_MESSAGES = 200     # fewer than this and a suggestion would be guesswork
    PREVIEW_FIRM_MARKS = 5         # until you have marked this many messages, the suggestion is an early guess...
    PREVIEW_EARLY_CAP = 70         # ...and never tougher than this

    def refresh_level_preview(self, force: bool = False):
        """Once a day, in the background at low priority: replay the last two days of the evidence log at
        each protection level, so the page can say what each level would have held. Nothing is changed."""
        if self._preview_busy or self.evidence is None or getattr(self, "standby", None) \
                or not self.cfg.get("level_preview", True):
            return
        now = time.time()
        if not force and now - self._preview_tried < self.PREVIEW_EVERY:
            return
        script = os.path.join(HERE, "replay.py")
        if not os.path.exists(script):
            return
        self._preview_tried = now
        self.evidence.flush(force=True)
        first_day = time.strftime("%Y-%m-%d", time.localtime(now - self.PREVIEW_SPAN - 86400))
        files = [f for f in self.evidence.files() if os.path.basename(f)[:10] >= first_day]
        if not files:
            return
        c = self.cfg
        # Only channels a replay can read without their keys: Public and hashtag channels. Private channel
        # keys never leave SpamGuard, so those messages are left out rather than misread.
        readable = [n for n, k in c["channels"].items() if n.startswith("#") or k == PUBLIC_CHANNEL_KEY]
        # your own settings, apart from the ones the level sets, and your exceptions: never keys or tokens
        base = {k: c[k] for k in profile_keys() if k in c and k not in PRESETS["balanced"]}
        base.update({"allow_hops": sorted(self.allow_hops), "allow_senders": sorted(self.allow_senders),
                     "allow_texts": sorted(self.allow_texts), "hashtag_channels": list(c.get("hashtag_channels") or [])})
        self._preview_busy = True

        def work():
            import tempfile
            folder = tempfile.mkdtemp(prefix="sg-preview-")
            started = time.time()
            try:
                path = os.path.join(folder, "base.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(base, f)
                cmd = [sys.executable, script, "--levels", ",".join(map(str, PREVIEW_LEVELS)), "--json",
                       "--since", str(int(now - self.PREVIEW_SPAN)), "--base", path,
                       "--only-channels", ",".join(readable), *files]
                if shutil.which("nice"):
                    cmd = ["nice", "-n", "19", *cmd]   # the radio's work always comes first
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=folder)
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or "").strip().splitlines()[-1:] or "replay failed")
                rep = json.loads(r.stdout.strip().splitlines()[-1])
                rep["ran"], rep["took"] = time.time(), round(time.time() - started)
                rep["suggested"] = suggest_level(rep)
                with self.lock:
                    self.level_preview = rep
                    self._save_state(force=True)
            except Exception as e:
                log.warning("Could not work out what each protection level would do: %s", e)
                with self.lock:
                    self.level_preview = dict(self.level_preview or {}, error="It couldn't be worked out this time. "
                                              "It will try again tomorrow.", failed=time.time())
            finally:
                shutil.rmtree(folder, ignore_errors=True)
                self._preview_busy = False

        threading.Thread(target=work, daemon=True, name="level-preview").start()

    def label_of(self, m: dict) -> Optional[str]:
        return self.labels.get(str(m.get("packet") or "")) or self.labels.get(f"{m.get('sender', '')}|{m.get('text', '')}")

    def preview_summary(self) -> dict:
        p = self.level_preview or {}
        marked = len(self.labels)
        out = {"running": bool(self._preview_busy), "enabled": self.evidence is not None,
               "switched_on": bool(self.cfg.get("level_preview", True)), "marked": marked,
               "ran": p.get("ran"), "error": p.get("error") if (p.get("failed") or 0) > (p.get("ran") or 0) else None}
        if p.get("levels"):
            out.update({k: p.get(k) for k in ("from", "to", "messages", "skipped", "labelled_spam", "labelled_fine", "took")})
            # your marks show straight away, not only after the next daily run
            out["levels"] = [dict(lv, check_items=[dict(m, label=self.label_of(m)) for m in lv.get("check_items") or []])
                             for lv in p["levels"]]
            sug = p.get("suggested")
            out["early"] = sug is not None and marked < self.PREVIEW_FIRM_MARKS
            out["suggested"] = min(sug, self.PREVIEW_EARLY_CAP) if out["early"] else sug
        return out

    def my_level_values(self) -> dict:
        """The values the level would set that you have set yourself (on the page or in the config file)."""
        return {k: self.settings.get(k, self.file_cfg.get(k)) for k in PRESETS["balanced"]
                if self.settings.get(k, self.file_cfg.get(k)) is not None}

    def refresh_public_map(self, force: bool = False):
        """Once a day, in the background, if switched on."""
        if not self.cfg.get("map_directory") or self._public_busy:
            return
        if not force and time.time() - self.public_reps["ts"] < 86400:
            return
        self._public_busy = True

        def work():
            try:
                req = urllib.request.Request(PUBLIC_MAP_URL, headers={"Accept": "application/json",
                                                                       "User-Agent": f"SpamGuard/{VERSION}"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    nodes = json.loads(r.read().decode("utf-8", "replace"))
                reps = self.parse_public_map(nodes, self.me, radio=self.radio)
                self.public_reps = {"ts": time.time(), "list": reps, "error": None}
                tmp = self._public_reps_path() + ".tmp"
                with open(tmp, "w") as f:
                    json.dump({"ts": self.public_reps["ts"], "list": reps}, f)
                os.replace(tmp, self._public_reps_path())
                log.info("Public MeshCore map: %d repeaters with a location nearby", len(reps))
            except Exception as e:
                self.public_reps["error"] = str(e)[:200]
                self.public_reps["ts"] = time.time() - 86400 + 3600  # try again in an hour
                log.info("Public MeshCore map not available: %s", e)
            finally:
                self._public_busy = False

        threading.Thread(target=work, daemon=True).start()

    def refresh_own_identities(self, force: bool = False):
        """This repeater's own companions (and room servers), from openHop, every 5 minutes. Their messages
        start here (no path), and SpamGuard leaves them alone."""
        now = time.time()
        if not force and now - getattr(self, "_own_checked", 0) < 300:
            return
        self._own_checked = now
        try:
            res = self._api("GET", "/api/identities", timeout=10)
            data = res.get("data", res) if isinstance(res, dict) else {}
        except Exception as e:
            log.debug("openHop identities not available: %s", e)
            return
        own: dict[str, dict] = {}
        for comp in data.get("configured_companions") or []:
            settings = comp.get("settings") or {}
            pk = str(comp.get("public_key") or "")
            for nm in {str(comp.get("name") or "").strip(), str(settings.get("node_name") or "").strip()}:
                if nm:
                    own[nm] = {"name": nm, "kind": "companion", "id": pk[:12].upper(), "hash": comp.get("hash")}
        for rs in data.get("configured") or []:
            settings = rs.get("settings") or {}
            pk = str(rs.get("public_key") or "")
            for nm in {str(rs.get("name") or "").strip(), str(settings.get("node_name") or "").strip()}:
                if nm:
                    own.setdefault(nm, {"name": nm, "kind": rs.get("type") or "room server", "id": pk[:12].upper(),
                                        "hash": rs.get("hash")})
        if set(own) != set(getattr(self, "own_names", {}) or {}):
            if own:
                self.note("This repeater's own companions: " + ", ".join(sorted(own)) + ". Their messages are never blocked.",
                          journal=False)
        self.own_names = own

    def own_summary(self) -> list[dict]:
        """One entry per own identity (its ID), with every name it goes by."""
        by: dict[str, dict] = {}
        for o in (getattr(self, "own_names", None) or {}).values():
            k = o.get("id") or o["name"]
            ent = by.setdefault(k, {"name": o["name"], "names": [], "kind": o.get("kind"), "id": o.get("id")})
            ent["names"].append(o["name"])
        for ent in by.values():
            ent["names"].sort()
            ent["name"] = " / ".join(ent["names"])
        return sorted(by.values(), key=lambda o: o["name"])

    def is_own(self, e) -> bool:
        """A message this repeater sent itself: it has no path, and the name is one of its own companions."""
        return getattr(e, "local", False) or (not e.path and e.sender in (getattr(self, "own_names", None) or {}))

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
        if (self.me or {}).get("lat") is None:
            self.repeaters["ts"] = now - 1800 + 60     # no location yet (openHop busy?): try again in a minute
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

    def release_duplicate(self, b: dict):
        """Forgive the copies of a duplicate block's message seen so far, instead of holding the block
        off: the next copy counts as a first copy again, and repeats after it are held back as usual."""
        v = b.get("value")
        k = "w:" + "|".join(v) if isinstance(v, list) else str(v)
        self.released[k] = time.time()

    def _released(self, e) -> bool:
        for k, ts in self.released.items():
            if e.ts > ts:
                continue
            if k.startswith("w:"):
                if all(w in e.text for w in k[2:].split("|")):
                    return True
            elif k in e.text:
                return True
        return False

    def covers_everyone(self, b: dict) -> bool:
        """Blocks that also stop people SpamGuard knows: these can't be kept for ever."""
        return b["kind"] in ("text", "words") or (b["kind"] == "hop" and self.hop_mode(b) == "contains")

    def gated(self, b: dict) -> bool:
        """Blocks that let known people through (written after the 'known people' rule)."""
        return b["kind"] in ("links", "lockdown", "route") or (b["kind"] == "hop" and self.hop_mode(b) == "contains_known") \
            or (b["kind"] in ("text", "words") and b.get("source") == "manual")

    def block_matches(self, b: dict, e: Event) -> bool:
        if self.gated(b) and self.is_known(e.sender):
            return False
        if b["kind"] == "lockdown":
            return True
        if b["kind"] == "links":
            return any(w in e.text for w in b["value"])
        if b["kind"] == "hop":
            if b.get("only_channel") and e.channel != b["only_channel"]:
                return False
            if self.hop_mode(b) in ("contains", "contains_known"):
                return b["value"] in e.path
            return ">".join(e.path) in (b.get("paths") or {})
        if b["kind"] == "route":
            if b.get("only_channel") and e.channel != b["only_channel"]:
                return False
            v = b["value"]
            return len(e.path) >= len(v) and all(self._same_hop(e.path[i], h) for i, h in enumerate(v))
        if b["kind"] == "repeat":
            return e.sender == b.get("who") and b["value"] in e.text
        if b.get("sender") and e.sender == b["sender"]:
            return False  # the original sender may re-send their own message
        if b["kind"] == "words":
            return all(w in e.text for w in b["value"])
        if b["kind"] == "suffix":
            suf = b["value"]
            return (len(e.path) == len(suf) + 1 and all(h in e.path for h in suf)
                    and e.first_hop not in self.allowed_origins(b))
        return b["value"] in e.text

    REPLAY_MIN_GAP = 30          # a copy within seconds is the mesh's own echo, not a replay
    REPLAY_MEMORY = 86400        # how long messages are remembered
    REPLAY_CLOCK_OFF = 6 * 3600  # a device clock this far out counts as wrong

    def replay_of(self, e: Event) -> bool:
        """Is this an old message sent again by another device? It must match a message first heard at
        least half a minute earlier (same channel, same text) from the same name or a cut-short copy of it,
        carry a different send time, and either have a badly wrong clock or the cut-short name. A person
        re-sending their own message gets a new, correct time and their full name, so isn't caught."""
        content = longest_piece(strip_mentions(e.text)).strip()
        if len(content) < 12:
            return False
        k = (e.channel, normalise(content))
        prev = self._texts.get(k)
        if prev is None or e.ts - prev[0] > self.REPLAY_MEMORY:
            self._texts[k] = (e.ts, e.sender, e.sent_ts)
            self._texts.move_to_end(k)
            while len(self._texts) > 5000:
                self._texts.popitem(last=False)
            return False
        first, who, sent = prev
        if e.ts - first < self.REPLAY_MIN_GAP or e.sent_ts == sent:
            return False
        cut_short = e.sender != who and len(e.sender.encode()) >= 12 and who.startswith(e.sender)
        clock_off = abs(e.ts - e.sent_ts) > self.REPLAY_CLOCK_OFF
        return (e.sender == who and clock_off) or cut_short

    def _caught_by_text(self, e) -> bool:
        b = self.blocks.get(e.matched) if e.matched else None
        return bool(b) and b["kind"] in ("text", "words", "repeat")

    def _match_event(self, e: Event, count: bool = True):
        if self.is_own(e):
            return   # openHop never applies SpamGuard's blocks to the repeater's own messages
        # Same order openHop checks the rules in (see build_rules).
        rank = {"manual": 0, "hop": 1, "campaign": 2, "dedupe": 3, "rotation": 9}
        for key, b in sorted(self.blocks.items(), key=lambda kv: (10 if self.gated(kv[1]) else rank.get(kv[1].get("source"), 2),
                                                                   -kv[1]["created"])):
            if e.ts >= b["created"] - 1 and self.block_matches(b, e):
                e.matched = key
                if count:
                    if b.get("source") == "dedupe" and not b.get("announced"):
                        b["announced"] = True
                        self.note(f"Stopped a copy sent under another name: {self.describe(b)}")
                        self.ev({"type": "block", "event": "start", "key": key, "kind": b["kind"], "value": b["value"],
                                 "source": "dedupe", "reason": b.get("reason"), "exempt_sender": b.get("sender")})
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
                ptype = int(p.get("type", -1))
            except (TypeError, ValueError):
                continue
            self.fg_observe(p)
            self._note_hash_size(p)
            if ptype == PAYLOAD_TYPE_ADVERT:
                self.learn_advert(p)
                continue
            if ptype != PAYLOAD_TYPE_GRP_TXT:
                continue
            key = str(p.get("packet_hash") or p.get("id"))
            if "transmitted" in p or "drop_reason" in p:
                v = self.verdict.setdefault(key, [False, False])
                v[0] = v[0] or bool(p.get("transmitted"))
                v[1] = v[1] or str(p.get("drop_reason") or "").startswith("Policy blocked")
                while len(self.verdict) > 5000:
                    self.verdict.popitem(last=False)
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
            # openHop records what this repeater sends itself with no path and no received signal
            e.local = (not e.path and "rssi" in p and "snr" in p and not p.get("rx_radio_id")
                       and not p.get("rssi") and not p.get("snr"))
            try:
                e.length = int(p.get("length") or 0) or len(payload) + 2 + len(e.path) * max(1, len((e.path or ["00"])[0]) // 2)
            except (TypeError, ValueError):
                e.length = len(payload)
            e.seen_at = now
            e.sent_ts = int(dec.get("sent") or 0)
            e.exempt = self.text_allowed(e.text) or self.is_own(e)
            e.replay = bool(self.cfg.get("replay_guard", True)) and not e.local and not e.exempt and self.replay_of(e)
            trusted = e.sender in self.allow_senders
            e.name_score = name_score(e.sender, self.name_res)
            # Unreadable text only counts from names SpamGuard doesn't know: a regular whose radio sends
            # one garbled message is not a spammer.
            e.garbage = e.garbage and bool(self.cfg.get("detect_garbage", True)) and not trusted \
                and not self.is_known(e.sender)
            e.random = not trusted and (e.name_score >= self.cfg["name_score_threshold"] or e.obfuscated or e.garbage)
            h = self.sender_history.setdefault(e.sender, {"first": ts, "count": 0, "hops": set()})
            if trusted and e.first_hop not in h["hops"] and h["hops"] and not any(
                    hops_related(e.first_hop, x) for x in h["hops"]):
                self.note(f"Trusted name '{e.sender}' arrived from a new place (first hop {e.first_hop}) - "
                          "names can be faked, so check this is really them")
            again = key in self.counted_packets  # read again after a restart: don't count it twice
            if not again and e.replay:
                self.stats["replays"] = self.stats.get("replays", 0) + 1
                self.replays.append(e.ts)
            if not again and not e.replay:   # a replayed copy says nothing about who is genuine
                h["count"] += 1
                self.counted_packets[key] = None
                while len(self.counted_packets) > 3000:
                    self.counted_packets.popitem(last=False)
            h["hops"].add(e.first_hop)
            if e.known_then is None:
                e.known_then = self.is_known(e.sender)
            if not e.replay and not e.local:
                self._note_slow_send(e)
            self._match_event(e, count=not again)
            if not e.matched and not again and not e.replay:
                home = h.setdefault("home", {})
                home[e.first_hop] = home.get(e.first_hop, 0) + 1   # where this person is usually heard from
            e.in_passing = self._held_in_passing(e)
            b = self.blocks.get(e.matched) if e.matched else None
            # Only blocks that hold PEOPLE back (repeater, route, link, lockdown), not spam-text blocks
            if b and not again and b["kind"] in PEOPLE_KINDS \
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
        keep = max(int(self.cfg.get("slow_repeat_window_seconds", 86400)), 3600) + 3600
        for k in [k for k, v in self.slow_sends.items() if not v["ts"] or v["ts"][-1] < now - keep]:
            del self.slow_sends[k]
        return new

    def _note_slow_send(self, e) -> None:
        """Remember each separate send of a long message by one name, for the day-long repeat limit. Copies
        of one send that arrive by different routes a moment apart count once."""
        c = self.cfg
        if not c.get("slow_repeat", True) or e.exempt or e.sender in self.allow_senders:
            return
        content = longest_piece(strip_mentions(e.text)).strip()
        if len(content) < int(c.get("dedupe_min_chars", 30)):
            return
        # "www" adds nothing to what a message says, and adding or dropping it shouldn't make a new message
        norm = " ".join(w for w in normalise(content).split() if w != "www")
        if len(norm) < 12:
            return
        key = f"{e.sender}|{e.channel}|" + hashlib.sha1(norm.encode(), usedforsecurity=False).hexdigest()[:12]
        rec = self.slow_sends.get(key)
        if rec is None:
            part = max(re.split(r"(?i)\bwww\b\.?", content), key=len)  # so the held text matches with or without "www."
            rec = self.slow_sends[key] = {"who": e.sender, "ch": e.channel, "snip": middle_chunk(part, c["text_rule_chars"]), "ts": []}
            while len(self.slow_sends) > 1500:
                self.slow_sends.pop(next(iter(self.slow_sends)))
        if rec["ts"] and abs(e.ts - rec["ts"][-1]) < 120:
            rec["ts"][-1] = max(rec["ts"][-1], e.ts)
        elif not rec["ts"] or e.ts > rec["ts"][-1]:
            rec["ts"].append(e.ts)
            del rec["ts"][:-40]

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
            return hops.setdefault(k, {"msgs": 0, "senders": set(), "random": set(), "garbage": set(), "new": set(),
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
            if e.garbage:
                h["garbage"].add(e.sender)
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
            g = len(h.get("garbage") or ())
            why.append(f"{len(h['random'])} random-looking names" + (f" ({g} sending unreadable text)" if g else ""))
        if len(h["new"]) >= c["hop_new_senders"]:
            why.append(f"{len(h['new'])} brand-new names")
        if len(h["campaign"]) >= c["hop_campaign_senders"]:
            why.append(f"{len(h['campaign'])} names sending the same spam")
        if len(h["random_long"]) >= c["hop_random_senders_long"]:
            why.append(f"{len(h['random_long'])} random names over {round(c['long_window_seconds'] / 3600, 1)} h")
        return why

    def _add_block(self, key, kind, value, reason, source, channel=None, ttl=None, from_ts=None,
                   action=None, match=None, sender=None, extra=None) -> bool:
        now = time.time()
        expires = (from_ts or now) + (ttl or self.cfg["block_ttl_seconds"])
        if kind in ("text", "words"):
            expires = min(expires, now + TEXT_BLOCK_MAX_SECONDS)
        if expires <= now:
            return False
        b = self.blocks.get(key)
        if b is None:
            self.blocks[key] = {"id": self._new_id(), "kind": kind, "value": value, "channel": channel,
                                "reason": reason, "source": source, "created": now, "expires": expires,
                                "hits": 0, "last_hit": None, "action": action, "match": match,
                                "manual": source == "manual", "sender": sender}
            if extra:
                self.blocks[key].update(extra)
            if kind == "hop":
                self.blocks[key]["paths"] = {}
            if kind == "suffix":
                self.blocks[key]["user_allowed"] = []
                self.blocks[key]["allow_ids"] = {}
            # The copy-paste guard sets one up for most longer messages, so it stays quiet until it
            # actually stops a copy (see _match_event); everything else is noted straight away.
            if source != "dedupe":
                self.note(f"Started blocking {self.describe(self.blocks[key])}: {reason[0].lower() + reason[1:]}")
                self._important = True
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
                return f"anything via repeater {b['value']}, except people it knows" + (
                    f" (only on {b['only_channel']})" if b.get("only_channel") else "")
            how = "messages starting at" if m == "exact_paths" else "anything via"
            return f"{how} repeater {b['value']}" + (f" (only on {b['only_channel']})" if b.get("only_channel") else "")
        if b["kind"] == "route":
            return f"messages that started on route {'>'.join(b['value'])}, except people it knows" + (
                f" (only on {b['only_channel']})" if b.get("only_channel") else "")
        if b["kind"] == "links":
            return "links from names SpamGuard doesn't know"
        if b["kind"] == "lockdown":
            return "lockdown: channel messages from names SpamGuard doesn't know"
        if b["kind"] == "suffix":
            route = ">".join(b["value"])
            return (f"new repeaters sending via {route}" if route
                    else "new repeaters right next to yours")
        if b["kind"] == "repeat":
            after = b.get("after") or []
            return f"more copies of \"{b['value']}\" from {b.get('who')}" + (
                f" (carrying on from {', '.join(after)})" if after else "")
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

    def established(self, name: str) -> bool:
        """Someone who has been chatting for a while under this name (whether or not they're 'known' yet)."""
        h = self.sender_history.get(name)
        return bool(h) and h["count"] >= 5 and h["first"] <= time.time() - 3600

    def rotation_candidates(self, window, campaigns=None) -> dict:
        """Routes receiving spam from several never-seen first repeaters. Only messages that really look
        like spam count: made-up or disguised names, or a campaign SpamGuard found suspicious (several
        regulars saying "good evening" is a conversation, not a campaign)."""
        campaigns = campaigns or {}
        out: dict[tuple, dict] = {}
        for e in window:
            if not e.path or self.known_origin(e.first_hop) or self.established(e.sender):
                continue
            sus_campaign = e.campaign is not None and (campaigns.get(e.campaign) or {}).get("suspect")
            if not (e.random or e.obfuscated or sus_campaign):
                continue
            d = out.setdefault(tuple(e.path[1:]), {"origins": set(), "senders": set()})
            d["origins"].add(e.first_hop)
            d["senders"].add(e.sender)
        return out

    def narrow_route(self, hop: str, h: dict, window, why: list[str]) -> Optional[tuple]:
        """When the only sign against a repeater is brand-new names and at least 80% of them started on one
        route (the first two repeaters), that route and how many names. Anything else (made-up names, a
        spam campaign, names spread over several routes, or a route too short to name) returns None and the
        whole repeater is blocked as before."""
        if len(why) != 1 or not why[0].endswith("brand-new names") or f"hop:{hop}" in self.blocks:
            return None
        per: dict[tuple, set] = {}
        for e in window:
            if e.first_hop == hop and e.sender in h["new"]:
                if len(e.path) < 2:
                    return None
                per.setdefault(tuple(e.path[:2]), set()).add(e.sender)
        if not per:
            return None
        route, names = max(per.items(), key=lambda kv: len(kv[1]))
        if len(names) < 0.8 * len(h["new"]) or len({len(x) for x in route}) != 1:
            return None
        return route, len(names)

    def route_surges(self, now: float) -> dict:
        """Routes (the first two repeaters) that suddenly carry many brand-new names. Looks at names, routes and
        timing only, never at what a message says. People SpamGuard knows, and routes already blocked, don't count."""
        c = self.cfg
        need = max(2, int(c.get("route_surge_names", 8)))
        cutoff = now - ROUTE_SURGE_SECONDS
        groups: dict[tuple, dict] = {}
        for e in self.events:
            if e.ts < cutoff or len(e.path) < 2:
                continue
            g = groups.setdefault(tuple(e.path[:2]), {"names": set(), "new": set(), "msgs": 0})
            g["msgs"] += 1
            if e.sender in self.allow_senders or self.is_known(e.sender):
                continue
            g["names"].add(e.sender)
            h = self.sender_history.get(e.sender)
            if h is None or h["count"] <= 2:
                g["new"].add(e.sender)
        out = {}
        for route, g in groups.items():
            if len(g["new"]) < need or len(g["new"]) < 0.6 * len(g["names"]):
                continue
            key = "route:" + ">".join(route)
            if key in self.blocks or f"hop:{route[0]}" in self.blocks or self.hop_allowed(route[0]):
                continue
            if self.suppressed.get(key, 0) > now:
                continue
            out[key] = {"route": list(route), "names": len(g["new"]), "messages": g["msgs"]}
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
                    want("words:" + hashlib.sha1("|".join(ws).encode(), usedforsecurity=False).hexdigest()[:10], "words", ws,
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
                        and not self._caught_by_text(e) and len(e.norm) >= c["dedupe_min_chars"] * 0.6 \
                        and not (self.released and self._released(e)):
                    v = variants.setdefault(e.norm, {"raws": set(), "last": 0, "ch": e.channel, "senders": set()})
                    v["raws"].add(e.text)
                    v["senders"].add(e.sender)
                    v["last"] = max(v["last"], e.ts)
            for _norm, v in variants.items():
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
                    want("words:" + hashlib.sha1("|".join(ws).encode(), usedforsecurity=False).hexdigest()[:10], "words", ws,
                         "Re-sent with emoji or symbols changed", "dedupe",
                         channel=v["ch"], ttl=c["dedupe_seconds"], from_ts=v["last"], sender=only)
            # Oldest first, so the rule remembers who sent the message originally.
            first: dict[str, Event] = {}
            last: dict[str, float] = {}
            for e in a["long"]:
                if e.ts < now - c["dedupe_seconds"]:
                    continue
                content = longest_piece(strip_mentions(e.text))
                if e.exempt or e.sender in self.allow_senders or len(content) < c["dedupe_min_chars"] \
                        or self._caught_by_text(e) or (self.released and self._released(e)):
                    continue  # already stopped by a text block: a second rule for the same message adds nothing
                snip = middle_chunk(content, c["text_rule_chars"])
                n = int(c["text_rule_chars"])
                if len(snip) < n <= len(content.strip()):
                    # whole words from the middle came out too short: take the characters as they come
                    body = content.strip()
                    snip = body[(len(body) - n) // 2:][:n]
                # A duplicate rule goes by duplicate suppression's own two lengths (which can go down to 5),
                # not by the shortest text a campaign rule may match.
                if len(snip) < min(c["min_rule_chars"], c["text_rule_chars"], c["dedupe_min_chars"]):
                    continue
                first.setdefault(snip, e)
                last[snip] = e.ts
            for snip, e in first.items():
                want(text_key(snip), "text", snip, "Copies under other names are blocked", "dedupe",
                     channel=e.channel, ttl=c["dedupe_seconds"], from_ts=last[snip], sender=e.sender)

        # 2b. One name sending the same message over and over: let the first few copies through, then stop
        # further copies of that message from that name for a while. (Never anything else they say.)
        if c.get("repeat_guard", True):
            groups: dict[tuple, list] = {}
            for e in a["long"]:
                if e.ts < now - c["repeat_window_seconds"] or e.exempt or e.sender in self.allow_senders:
                    continue
                content = longest_piece(strip_mentions(e.text)).strip()
                if len(content) < 8:
                    continue
                groups.setdefault((e.sender, e.channel, normalise(content)), []).append((e, content))
            for (who, ch, _), evs in groups.items():
                if len({x[0].packet for x in evs}) <= int(c["repeat_max"]):
                    continue
                snip = middle_chunk(evs[-1][1], c["text_rule_chars"])
                key = "repeat:" + hashlib.sha1(f"{who}|{snip}".encode(), usedforsecurity=False).hexdigest()[:10]
                if self.suppressed.get(key, 0) > now:
                    continue
                if self._add_block(key, "repeat", snip, f"Sent {len(evs)} times in a few minutes", "repeat",
                                   channel=ch, ttl=int(c["repeat_block_seconds"]), from_ts=evs[-1][0].ts,
                                   extra={"who": who}):
                    changed = True

        # 2b''. Slow repeating: the same long message from one name, spread over hours so the quick check above
        # never sees it. Counts separate sends over a day; further copies are held for a few hours, and one
        # gets through each time the hold ends while they keep at it. Only repeats are counted, never content.
        if c.get("slow_repeat", True):
            win_s = int(c["slow_repeat_window_seconds"])
            # A name that takes over sending the same message after another name has stopped (someone
            # changing their name to start the count again) carries on that name's count. Two people who
            # post the same thing at overlapping times are still counted separately.
            same: dict[str, list] = {}
            for skey, rec in self.slow_sends.items():
                same.setdefault(skey.rsplit("|", 2)[-1] + "|" + str(rec["ch"]), []).append(rec)
            for skey, rec in self.slow_sends.items():
                recent = [t for t in rec["ts"] if t >= now - win_s]
                if not recent:
                    continue
                own = len(recent)
                after = []
                for other in same.get(skey.rsplit("|", 2)[-1] + "|" + str(rec["ch"]), ()):
                    if other is rec or not other["ts"] or other["ts"][-1] >= recent[0]:
                        continue
                    theirs = [t for t in other["ts"] if t >= now - win_s]
                    if theirs:
                        recent = theirs + recent
                        if other["who"] not in after:
                            after.append(other["who"])
                if len(recent) <= int(c["slow_repeat_max"]):
                    continue
                reason = f"Sent {len(recent)} times today" + ("" if own == len(recent) else ", partly under another name")
                key = "slowrepeat:" + hashlib.sha1(skey.encode(), usedforsecurity=False).hexdigest()[:10]
                if self.suppressed.get(key, 0) > now:
                    continue
                if self._add_block(key, "repeat", rec["snip"], reason, "slowrepeat",
                                   channel=rec["ch"], ttl=int(c["slow_repeat_hold_seconds"]), from_ts=max(recent),
                                   extra={"who": rec["who"], "after": after[:5]} if after else {"who": rec["who"]}):
                    changed = True
                if after and len(recent) > int(c["slow_repeat_max"]):
                    old = self.name_links.get(rec["who"], {}).get("after", [])
                    self.name_links[rec["who"]] = {"after": (old + [a for a in after if a not in old])[:10], "ts": now}

        # 2b'. Replays: further copies of an old message being sent again, from that name only.
        if c.get("replay_guard", True):
            for e in a["long"]:
                if not e.replay or e.matched:
                    continue
                content = longest_piece(strip_mentions(e.text)).strip()
                snip = middle_chunk(content, c["text_rule_chars"])
                key = "replay:" + hashlib.sha1(f"{e.sender}|{snip}".encode(), usedforsecurity=False).hexdigest()[:10]
                if self.suppressed.get(key, 0) > now:
                    continue
                if self._add_block(key, "repeat", snip, "An old message being sent again by another device", "replay",
                                   channel=e.channel, ttl=6 * 3600, from_ts=e.ts, extra={"who": e.sender}):
                    changed = True

        # 2c. A campaign block that keeps catching regulars (people SpamGuard knows, heard from where they
        # usually are) is ordinary chat, not spam: stop it. Someone copying a regular's name usually comes
        # from somewhere else, so that doesn't count.
        for key, b in list(self.blocks.items()):
            if b.get("source") != "campaign":
                continue
            caught = {e.sender for e in a["long"] if e.matched == key and self.is_known(e.sender)
                      and (self.sender_history.get(e.sender, {}).get("home") or {}).get(e.first_hop, 0) >= 3}
            if len(caught) >= 3:
                self.blocks.pop(key)
                self.suppressed[key] = now + 86400
                self.note(f"Stopped blocking {self.describe(b)}: it was catching {len(caught)} regulars, so it looks like ordinary chat")
                changed = True

        # 2d. A big flood of made-up names through many repeaters at once: a short automatic lockdown
        # (only people SpamGuard knows get through) until single-repeater blocks can catch up.
        if c.get("auto_lockdown", True) and "lockdown" not in self.blocks and self.suppressed.get("lockdown", 0) <= now:
            recent = [e for e in a["window"] if e.ts >= now - 120 and e.random and not self.is_known(e.sender)]
            names = {e.sender for e in recent}
            entries = {e.first_hop for e in recent}
            if len(names) >= 12 and len(entries) >= 6:
                self._add_block("lockdown", "lockdown", None,
                                f"Automatic 15-minute lockdown: {len(names)} made-up names through {len(entries)} repeaters in two minutes",
                                "auto-lockdown", ttl=900)
                self._important = True
                self.note(f"Flood of {len(names)} made-up names through {len(entries)} repeaters: only people SpamGuard knows get through for 15 minutes")
                changed = True

        # 3. Source repeater blocking.
        if c.get("enable_hop_rules", True):
            for hop, h in a["hops"].items():
                if hop == "DIRECT" or self.hop_allowed(hop):
                    continue
                why = self.hop_signals(h)
                if why:
                    # Only brand-new names, nearly all on one route: block that route, which is narrower than
                    # everything through the repeater, and leave other routes through it alone.
                    narrow = self.narrow_route(hop, h, a["window"], why) if c.get("hop_prefer_route", True) else None
                    if narrow:
                        route, n = narrow
                        want("route:" + ">".join(route), "route", list(route),
                             f"{n} brand-new names started on this route (narrower than blocking repeater {hop})",
                             "hop-route", ttl=int(c.get("hop_block_ttl_seconds", 7200)))
                        continue
                    reason = why[0][0].upper() + why[0][1:] + (f" (and {len(why) - 1} other sign{'s' if len(why) > 2 else ''})" if len(why) > 1 else "")
                    want(f"hop:{hop}", "hop", hop, reason, "hop", ttl=int(c.get("hop_block_ttl_seconds", 7200)))

        # 3b. A route that suddenly carries many brand-new names (a spammer who keeps changing names but
        # always starts on the same first repeaters): suggest blocking it, or do so if you allowed that.
        if c.get("route_surge", True):
            found = self.route_surges(now)
            ttl = int(c.get("route_surge_ttl", 7200))
            auto = sum(1 for b in self.blocks.values() if b.get("source") == "route-auto")
            for key, d in found.items():
                if c.get("route_auto") and auto < ROUTE_AUTO_MAX:
                    want(key, "route", d["route"],
                         f"{d['names']} brand-new names started on this route within {ROUTE_SURGE_SECONDS // 60} minutes",
                         "route-auto", ttl=ttl)
                    auto += 1
                    found = {k: v for k, v in found.items() if k != key}
            for key in list(self.route_suggest):
                if key not in found:
                    del self.route_suggest[key]
            for key, d in found.items():
                if key not in self.route_suggest:
                    self.note(f"Route {'>'.join(d['route'])} suddenly carries {d['names']} brand-new names. Open Blocks to see the suggestion.")
                    self._important = True
                self.route_suggest[key] = dict(d, first=self.route_suggest.get(key, {}).get("first", now))
        elif self.route_suggest:
            self.route_suggest = {}

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
            for suf, d in self.rotation_candidates(a["window"], a["campaigns"]).items():
                need = 2 if suf in linked else c["rotate_first_hops"]
                if len(suf) <= 1 and suf not in linked:
                    need *= 2   # a route of one repeater next to yours carries a lot of genuine traffic: be surer
                # Never block a route that people who have been chatting for a while depend on.
                regulars = {e.sender for e in a["long"] if e.path and tuple(e.path[1:]) == suf
                            and self.established(e.sender) and not e.random}
                if len(regulars) >= 3:
                    continue
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

        # Blocks that stop everyone, people SpamGuard knows included, never last more than a week from now
        # (a repeater block on 'anything passing through', or text). Others can be kept until removed.
        for b in self.blocks.values():
            if self.covers_everyone(b) and b["expires"] - now > TEXT_BLOCK_MAX_SECONDS + 60:
                b["expires"] = now + TEXT_BLOCK_MAX_SECONDS
        for k in [k for k, b in self.blocks.items() if b["expires"] <= now]:
            b = self.blocks.pop(k)
            if b.get("source") != "dedupe":
                self._important = True
                self.note(f"Stopped blocking {self.describe(b)} (expired after {b.get('hits', 0)} catches)")
            changed = True
        for k in [k for k, v in self.suppressed.items() if v <= now]:
            del self.suppressed[k]
        for k in [k for k, v in self.released.items() if v < now - 86400]:
            del self.released[k]
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
        self.hops_stale = 0
        self._route_prep()
        if self.cfg.get("paused"):
            return [], []
        tail: list[dict] = []
        for key, b in sorted(self.blocks.items(), key=lambda kv: kv[1]["id"]):
            if b["kind"] != "suffix":
                continue
            per = [self._hop_forms(h) for h in b["value"]]
            sizes = [z for z in self._sizes_now if all(z in f for f, _, _ in per)]
            self._route_count(any(nw for _, nw, _ in per), any(sh for _, _, sh in per), bool(sizes))
            ids = b.setdefault("allow_ids", {})
            origins = sorted(self.allowed_origins(b))[: int(self.cfg["max_origins_per_route"])]
            for size in sizes:
                suf = [f[size] for f, _, _ in per]
                first = size == sizes[0]
                tag = "" if first else f"@{size}"
                for o in origins:
                    # an exception only ever lets more through, so it is shortened freely
                    oh = o.upper()[: 2 * size] if len(o) >= 2 * size else None
                    if oh is None:
                        continue
                    if first:
                        if o not in ids:
                            ids[o] = self._new_id()
                        aid = ids[o]
                    else:
                        aid = self._size_id(b, f"allow:{o}{tag}")
                    tail.append({"id": aid, "name": f"{RULE_PREFIX}{key}:allow:{o}{tag}", "enabled": True,
                                 "if": {"all": [
                                     {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                     {"field": "path_hashes", "op": "equals", "value": [oh] + suf}]},
                                 "then": {"action": "allow"}})
                tail.append({"id": b["id"] if first else self._size_id(b, str(size)),
                             "name": f"{RULE_PREFIX}{key}{tag}" + self._rule_label(b), "enabled": True,
                             "if": {"all": [
                                 {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                 {"field": "hop_count", "op": "equals", "value": len(suf) + 1}]
                                 + [{"field": "path_hashes", "op": "contains", "value": h} for h in suf]},
                             "then": {"action": self.rule_action(b)}})
        # Hard ceiling on everything SpamGuard writes, however many blocks a spam wave creates: too many
        # rules can overload openHop (a tester saw its database lock up at ~740 rules from a similar tool).
        # Repeater, links and lockdown blocks (and their known-people rule) come first; the main list,
        # whose oldest duplicate rules go first, gets what is left. Trimming the tail from the end drops
        # the newest blocks first and never an 'allow' without the block below it.
        cap = int(self.cfg["max_total_rules"])
        # FloodGuard's rules sit straight after the known-people rule, so channel messages from people
        # SpamGuard knows always get through, and before the other blocks, so the rule limit never drops them.
        gated, flood = self._build_gated(), self._build_flood()
        if flood:
            gated = (gated[:1] if gated else [self._known_rule()]) + flood + gated[1:]
        tail = self._not_own(tail + gated)
        # Standing rules are never pushed out by the limit, however many blocks a spam wave creates: the
        # wardriving rule, FloodGuard's rules and the known-people rule they rely on. They count towards
        # the limit; the blocks share what is left.
        wd = self._not_own(self._build_wardrive())
        keep_ids = {r["id"] for r in flood}
        if flood:
            keep_ids.add(self._rid("known:*"))
        budget = max(0, cap - len(wd))
        if len(tail) > budget:
            while len(tail) > budget:
                drop = next((i for i in range(len(tail) - 1, -1, -1) if tail[i]["id"] not in keep_ids), None)
                if drop is None:
                    break
                del tail[drop]
            if len(tail) == 1 and "known-people" in str(tail[0].get("name")):
                tail = []
            if not self.stats.get("rule_limit_warned"):
                self.stats["rule_limit_warned"] = 1
                self.note(f"Rule limit ({cap}) reached - the newest blocks were left out of openHop")
        main = wd + self._not_own(self._build_main(max(0, cap - len(tail) - len(wd))))
        return main, tail

    @staticmethod
    def _not_own(rules: list[dict]) -> list[dict]:
        """SpamGuard's blocks never apply to messages this repeater sends itself (its own companions and
        room servers): openHop tells the rules so (local_transmission), and that can't be faked over the air.
        'not_equals true' also matches on an older openHop that doesn't say, so nothing is lost there."""
        for r in rules:
            if (r.get("then") or {}).get("action") in ("drop", "log_only"):
                conds = r.setdefault("if", {}).setdefault("all", [])
                if not any(c.get("field") == "local_transmission" for c in conds):
                    conds.append({"field": "local_transmission", "op": "not_equals", "value": True})
        return rules

    def _rid(self, key: str) -> int:
        if key not in self.rule_ids:
            self.rule_ids[key] = self._new_id()
        return self.rule_ids[key]

    # ---- wardriving pings
    MAPPER_PREFIX = "@[MapperBot]"   # how MeshMapper pings start
    MAPPER_PREFIXES = ("@[MapperBot]", "MM:")   # MeshRank shows current MeshMapper pings as "MM:..."

    WARDRIVE_CHANNEL = "#wardriving"   # the channel MeshMapper uses; not configurable

    def wardrive_channels(self) -> dict[str, str]:
        """The wardriving channel to leave unrepeated, name -> key."""
        return {self.WARDRIVE_CHANNEL: hashtag_secret(self.WARDRIVE_CHANNEL)}

    def wardrive_collisions(self) -> list[str]:
        """Wardriving channels whose one-byte channel code is shared with a channel openHop can read. A packet
        only carries that byte, so for those the rule also checks the message looks like a MeshMapper ping."""
        known = dict(self.cfg.get("channels") or {})
        known.update(getattr(self, "openhop_channels", {}) or {})
        out = []
        for name, key in self.wardrive_channels().items():
            hb = channel_hash_byte(key)
            if any(channel_hash_byte(k) == hb and k.lower() != key for k in known.values() if isinstance(k, str)):
                out.append(name)
        return out

    def _build_wardrive(self) -> list[dict]:
        """Don't repeat wardriving pings (off by default). Only readable messages on those channels; this
        repeater's own companions are never affected (_not_own)."""
        c = self.cfg
        if not c.get("wardrive_block"):
            return []
        act = "drop" if c["mode"] == "protect" else "log_only"
        clash = set(self.wardrive_collisions())
        rules = []
        for name, key in sorted(self.wardrive_channels().items()):
            conds = [{"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                     {"field": "channel_hash", "op": "equals", "value": key},
                     {"field": "channel_decryptable", "op": "equals", "value": True}]
            if name not in clash:
                rules.append({"id": self._rid(f"wardrive:{key}"), "name": f"{RULE_PREFIX}wardriving pings on {name}",
                              "enabled": True, "if": {"all": conds}, "then": {"action": act}})
                continue
            # The engine only nests one level, so a shared channel code gets one rule per ping form.
            for i, pre in enumerate(self.MAPPER_PREFIXES):
                rid_key = f"wardrive:{key}" if i == 0 else f"wardrive:{key}:{i}"
                rules.append({"id": self._rid(rid_key), "name": f"{RULE_PREFIX}wardriving pings on {name}",
                              "enabled": True, "if": {"all": conds + [{"field": "channel_message_body",
                                                                      "op": "starts_with", "value": pre}]},
                              "then": {"action": act}})
        return rules

    def wardrive_rule_ids(self) -> set:
        return {v for k, v in self.rule_ids.items() if k.startswith("wardrive:")}

    def _known_rule(self) -> dict:
        return {"id": self._rid("known:*"), "name": f"{RULE_PREFIX}known-people", "enabled": True,
                "if": {"all": [{"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                               {"field": "channel_decryptable", "op": "equals", "value": True},
                               {"field": "channel_sender", "op": "in", "value": "@spamguard.known_senders"}]},
                "then": {"action": "allow"}}

    def _build_flood(self) -> list[dict]:
        """FloodGuard's rules: the flood limit while a flood is being contained, and the fixed hop limits
        for unscoped flood packets and adverts (MeshCore's flood.max.unscoped and flood.max.advert).
        They look only at how a packet travels (flood or direct, hops so far, adverts), never at who
        sent it or what it says. Direct (routed) packets are never touched."""
        c = self.cfg
        if not c.get("floodguard"):
            return []
        act = "drop" if c["mode"] == "protect" and self.fg_can_act() else "log_only"
        flood = {"field": "route_type", "op": "in", "value": [ROUTE_TRANSPORT_FLOOD, ROUTE_FLOOD]}
        rules = []
        lim = self.fg.get("limit")
        if lim:
            rules.append({"id": self._rid("flood:limit"), "name": f"{RULE_PREFIX}flood-limit (floodguard, {lim}+ hops)",
                          "enabled": True, "if": {"all": [flood, {"field": "hop_count", "op": "gte", "value": int(lim)}]},
                          "then": {"action": act}})
        u = int(c.get("flood_max_unscoped") or 0)
        if u:
            rules.append({"id": self._rid("flood:unscoped"),
                          "name": f"{RULE_PREFIX}flood-max-unscoped (floodguard, {u}+ hops)", "enabled": True,
                          "if": {"all": [{"field": "route_type", "op": "equals", "value": ROUTE_FLOOD},
                                         {"field": "hop_count", "op": "gte", "value": u}]},
                          "then": {"action": act}})
        a = int(c.get("flood_max_advert") or 0)
        if a:
            rules.append({"id": self._rid("flood:advert"),
                          "name": f"{RULE_PREFIX}flood-max-advert (floodguard, {a}+ hops)", "enabled": True,
                          "if": {"all": [flood, {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_ADVERT},
                                         {"field": "hop_count", "op": "gte", "value": a}]},
                          "then": {"action": act}})
        return rules

    def _build_gated(self) -> list[dict]:
        """Blocks that let known people through: first one 'allow' rule for names on SpamGuard's known
        list (an openHop object), then the blocks themselves. openHop stops at the first rule that matches,
        so a known name never reaches the blocks below it. One rule each, whatever the number of channels:
        they apply to every channel openHop can read (SpamGuard gives openHop its channel keys)."""
        gated = sorted(((k, b) for k, b in self.blocks.items() if self.gated(b)), key=lambda kv: kv[1]["id"])
        if not gated:
            return []
        readable = [{"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                    {"field": "channel_decryptable", "op": "equals", "value": True}]
        rules: list[dict] = [self._known_rule()]
        for key, b in gated:
            ids = b.setdefault("ids", {})
            only = self._channel_cond(b)
            if b["kind"] == "links":
                conds = [(w, [{"field": "channel_message_body", "op": "contains", "value": w}]) for w in b["value"]]
            elif b["kind"] == "hop":
                forms, nw, sh = self._hop_forms(b["value"])
                self._route_count(nw, sh, bool(forms))
                if not forms:
                    continue
                first = min(forms)
                conds = [("" if z == first else f"{z}b", [{"field": "path_hashes", "op": "contains", "value": forms[z]}])
                         for z in sorted(forms)]
            elif b["kind"] == "route":
                # openHop can check that a route passes through repeaters but not yet in which order, so the
                # rule asks for all of them. SpamGuard's own records check the order exactly.
                per = [self._hop_forms(h) for h in b["value"]]
                sizes = [z for z in self._sizes_now if all(z in f for f, _, _ in per)]
                self._route_count(any(nw for _, nw, _ in per), any(sh for _, _, sh in per), bool(sizes))
                if not sizes:
                    continue
                conds = [("" if z == sizes[0] else f"{z}b", [{"field": "path_hashes", "op": "contains", "value": f[z]} for f, _, _ in per])
                         for z in sizes]
            elif b["kind"] in ("text", "words"):
                secret = self.cfg["channels"].get(b.get("channel") or "", PUBLIC_CHANNEL_KEY)
                words = b["value"] if b["kind"] == "words" else [b["value"]]
                conds = [("", [{"field": "channel_hash", "op": "equals", "value": secret}]
                          + [{"field": "channel_message_body", "op": "contains", "value": w} for w in words])]
            else:  # lockdown
                conds = [("", [])]
            for sub, extra in conds:
                rk = f"*|{sub}"
                if rk not in ids:
                    ids[rk] = self._new_id()
                rules.append({"id": ids[rk], "name": f"{RULE_PREFIX}{key}" + (f":{sub}" if sub else "") + self._rule_label(b),
                              "enabled": True, "if": {"all": readable + only + extra},
                              "then": {"action": self.rule_action(b)}})
        return rules

    RULE_ORIGIN = {"manual": "yours", "dedupe": "duplicate", "repeat": "repeating", "slowrepeat": "repeating all day", "replay": "replayed", "campaign": "campaign",
                   "rotation": "changing identity", "hop": "auto",
                   "auto-lockdown": "auto lockdown", "lockdown": "yours"}

    @staticmethod
    def _named_channels(objs: dict) -> dict[str, str]:
        """Channels openHop's policy settings already name, with their keys (objects.channels, as a
        name -> key map or a list of {name, secret}). Offered on the page so you can pick the ones
        SpamGuard should read without looking keys up again. Keys never leave this machine's page."""
        out: dict[str, str] = {}
        ch = objs.get("channels") if isinstance(objs, dict) else None
        items = ch.items() if isinstance(ch, dict) else ((None, x) for x in ch) if isinstance(ch, (list, tuple)) else ()
        for name, v in items:
            if isinstance(v, dict):
                name = v.get("name") or name
                v = v.get("secret") or v.get("key") or v.get("psk") or v.get("channel_secret")
            if isinstance(name, str) and name.strip() and isinstance(v, str) \
                    and re.fullmatch(r"[0-9a-f]{32}|[0-9a-f]{64}", v.strip().lower()):
                out[name.strip()[:40]] = v.strip().lower()
        return out

    def rule_numbers(self, b: dict) -> list:
        """The openHop rule ids for a block. openHop's packet feed says "Policy blocked packet (rule N)"."""
        ids = list((b.get("ids") or {}).values()) if self.gated(b) else \
            [b.get("id")] + list((b.get("paths") or {}).values()) + list((b.get("size_ids") or {}).values())
        return sorted({i for i in ids if isinstance(i, int)})

    def _rule_label(self, b: dict) -> str:
        """A readable tail for the rule name, so openHop's packet list says what stopped a packet and
        whether it was a block you added or one SpamGuard made. Rule ids don't change with it."""
        origin = self.RULE_ORIGIN.get(b.get("source"), "auto")
        kind = b.get("kind")
        v = b.get("value")
        if kind == "text":
            what = 'text "' + re.sub(r"\s+", " ", str(v))[:24] + '"'
        elif kind == "repeat":
            what = "repeats by " + str(b.get("who") or "")[:20]
        elif kind == "hop":
            what = "via " + str(v)
        elif kind == "route":
            what = "route " + ">".join(v)
        elif kind == "words":
            what = "words " + "+".join(str(w) for w in v)[:24]
        else:
            what = str(kind or "")
        where = f" on {b['only_channel']}" if b.get("only_channel") else ""
        return f" ({origin}) {what}{where}".rstrip()

    def _channel_cond(self, b: dict) -> list[dict]:
        """A block you limited to one channel only applies there."""
        ch = b.get("only_channel")
        secret = self.cfg["channels"].get(ch) if ch else None
        return [{"field": "channel_hash", "op": "equals", "value": secret}] if secret else []

    def _build_main(self, limit: int | None = None) -> list[dict]:
        rank = {"manual": 0, "hop": 1, "campaign": 2, "dedupe": 3}
        order = sorted(((k, b) for k, b in self.blocks.items() if b["kind"] != "suffix" and not self.gated(b)),
                       key=lambda kv: (rank.get(kv[1].get("source"), 2), -kv[1]["created"]))
        rules: list[dict] = []
        limit = int(self.cfg["max_total_rules"]) if limit is None else max(0, limit)
        for key, b in order:
            if len(rules) >= limit:
                break
            if b["kind"] == "hop" and self.hop_mode(b) == "exact_paths":
                for ps, pid in sorted((b.get("paths") or {}).items(), key=lambda kv: kv[1]):
                    per = [self._hop_forms(h) for h in ps.split(">")]
                    sizes = [z for z in self._sizes_now if all(z in f for f, _, _ in per)]
                    self._route_count(any(nw for _, nw, _ in per), any(sh for _, _, sh in per), bool(sizes))
                    for size in sizes:
                        first = size == sizes[0]
                        tag = "" if first else f"@{size}"
                        rules.append({"id": pid if first else self._size_id(b, f"{ps}{tag}"),
                                      "name": f"{RULE_PREFIX}{key}:{ps}{tag}" + self._rule_label(b), "enabled": True,
                                      "if": {"all": [
                                          {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                          {"field": "path_hashes", "op": "equals", "value": [f[size] for f, _, _ in per]}]
                                          + self._channel_cond(b)},
                                      "then": {"action": self.rule_action(b)}})
                continue
            if b["kind"] == "hop":
                forms, nw, sh = self._hop_forms(b["value"])
                self._route_count(nw, sh, bool(forms))
                first = min(forms) if forms else None
                for size in sorted(forms):
                    tag = "" if size == first else f"@{size}"
                    rules.append({"id": b["id"] if size == first else self._size_id(b, str(size)),
                                  "name": f"{RULE_PREFIX}{key}{tag}" + self._rule_label(b), "enabled": True,
                                  "if": {"all": [
                                      {"field": "payload_type", "op": "equals", "value": PAYLOAD_TYPE_GRP_TXT},
                                      {"field": "path_hashes", "op": "contains", "value": forms[size]}]
                                      + self._channel_cond(b)},
                                  "then": {"action": self.rule_action(b)}})
                continue
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
                cond["all"].append({"field": "channel_sender", "op": "not_equals", "value": oh_sender(b["sender"])})
            if b["kind"] == "repeat":
                cond["all"].append({"field": "channel_sender", "op": "equals", "value": oh_sender(b.get("who"))})
            rules.append({"id": b["id"], "name": f"{RULE_PREFIX}{key}" + self._rule_label(b), "enabled": True,
                          "if": cond, "then": {"action": self.rule_action(b)}})
        if len(rules) >= limit and not self.stats.get("rule_limit_warned"):
            self.stats["rule_limit_warned"] = 1
            self.note(f"Rule limit ({limit}) reached - oldest duplicate rules were left out")
        return rules[:limit]

    # ---- which SpamGuard is in charge of this repeater ----
    @property
    def instance_id(self) -> str:
        """A random id for this copy of SpamGuard, kept next to its state file (never in it, so a copy
        that imports another's state still has its own id)."""
        if getattr(self, "_instance_id", None):
            return self._instance_id
        path = os.path.splitext(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])[0] + ".instance.json"
        iid = None
        try:
            with open(path) as f:
                iid = str(json.load(f).get("id") or "") or None
        except (OSError, ValueError):
            pass
        if not iid:
            iid = os.urandom(6).hex()
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w") as f:
                    json.dump({"id": iid}, f)
            except OSError:
                pass
        self._instance_id = iid
        return iid

    def owner_marker(self, state: str = "active", to: Optional[str] = None) -> dict:
        m = {"id": self.instance_id, "kind": install_kind(), "host": socket.gethostname()[:40],
             "version": VERSION, "state": state, "ts": round(time.time())}
        if to:
            m["to"] = to
        return m

    def describe_owner(self, o: dict) -> str:
        what = KIND_NAMES.get(str(o.get("kind")), "another copy")
        host = str(o.get("host") or "")
        return f"{what}{' on ' + host if host else ''}"

    def _lease_blocks_me(self, owner: Optional[dict]) -> bool:
        """True while another copy of SpamGuard holds this repeater."""
        if not isinstance(owner, dict) or not owner.get("id") or owner.get("id") == self.instance_id:
            return False
        if time.time() - float(owner.get("ts") or 0) >= LEASE_SECONDS:
            return False  # it stopped refreshing: it has gone
        if owner.get("state") == "released":
            return bool(owner.get("to")) and owner.get("to") != self.instance_id
        return True

    def sync_policy(self, force: bool = False) -> bool:
        if getattr(self, "retired", False):
            return False
        res = self._api("GET", "/api/policy")
        data = res.get("data", res)
        pe = dict(data.get("policy_engine") or {})
        objs0 = pe.get("objects") if isinstance(pe.get("objects"), dict) else {}
        self.openhop_channels = self._named_channels(objs0)
        owner = objs0.get(OWNER_KEY) if isinstance(objs0.get(OWNER_KEY), dict) else None
        if self._lease_blocks_me(owner):
            if not getattr(self, "standby", None):
                self.note(f"Another SpamGuard ({self.describe_owner(owner)}) is already looking after this repeater, "
                          "so this one is waiting and won't change openHop's rules")
            self.standby = dict(owner)
            self.sync_pending = False
            self.last_sync = time.time()
            return False
        if getattr(self, "standby", None) or (owner and owner.get("id") != self.instance_id):
            prev = getattr(self, "standby", None) or owner
            self.note(f"Took over this repeater from {self.describe_owner(prev)}")
        self.standby = None
        now = time.time()
        refresh_owner = (not owner or owner.get("id") != self.instance_id or owner.get("state") != "active"
                         or now - float(owner.get("ts") or 0) > LEASE_REFRESH)
        existing = [r for r in (pe.get("rules") or []) if isinstance(r, dict)]
        user_rules = [r for r in existing if not str(r.get("name", "")).startswith(RULE_PREFIX)]
        ours_now = [r for r in existing if str(r.get("name", "")).startswith(RULE_PREFIX)]
        self.rules_seen = len(ours_now)
        main, tail = self.build_rule_sets()
        ours_new = main + tail
        self.rule_summary = {"after_yours": bool(self.cfg.get("rules_after_yours")), "yours": len(user_rules),
                             "rules": [[r.get("id"), r.get("name"), (r.get("then") or {}).get("action"), plain_rule(r)] for r in ours_new]}
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
        # The channel keys SpamGuard reads, as one openHop object group, so openHop can read those channels and
        # SpamGuard's rules need not be repeated for every channel (a few hundred channels used to mean a few
        # hundred copies of some rules).
        groups = dict(objects.get("channel_hash_groups") or {}) if isinstance(objects.get("channel_hash_groups"), dict) else {}
        keys_now = groups.get("spamguard")
        keys_new = sorted(set(self.cfg["channels"].values())) if ours_new else None
        if keys_new:
            groups["spamguard"] = keys_new
        else:
            groups.pop("spamguard", None)
        if groups:
            objects["channel_hash_groups"] = groups
        else:
            objects.pop("channel_hash_groups", None)
        objects[OWNER_KEY] = self.owner_marker() if refresh_owner else owner
        pe["objects"] = objects
        # Where SpamGuard's rules sit: normally before your own (so a broad 'allow' of yours can't let spam
        # past), or after them if you asked for that (Advanced, Timing).
        want = (user_rules + main + tail) if self.cfg.get("rules_after_yours") else (main + user_rules + tail)
        same_order = [r.get("id") for r in existing] == [r.get("id") for r in want]
        if not force and not needs_enable and obj_now == obj_new and keys_now == keys_new and not refresh_owner \
                and same_order and json.dumps(ours_now, sort_keys=True) == json.dumps(ours_new, sort_keys=True):
            self.sync_pending = False
            return False
        if not force and self.rules_expected is not None and len(ours_now) != self.rules_expected:
            self.self_heals += 1
            self.note(f"openHop had {len(ours_now)} SpamGuard rules instead of {self.rules_expected} - put them back")
        pe["rules"] = want
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

    def backfill_adverts(self):
        """Once after starting, read the last week of adverts from openHop so the map can place spam
        straight away instead of waiting for adverts to arrive. Asking openHop for a whole week of one
        packet type takes it over 30 seconds on a Pi, so this runs in the background, 12 hours at a
        time, newest first. If a slice fails, the whole read is tried again an hour later."""
        if self._adv_backfill and (self._adv_backfill > 1 or time.time() + self._adv_backfill < 3600):
            return
        if getattr(self, "_adv_backfill_busy", False):
            return
        self._adv_backfill_busy = True

        def work():
            ok, total, end = True, 0, time.time()
            try:
                for _ in range(14):
                    start = end - 43200
                    rows = None
                    for _attempt in range(2):
                        try:
                            res = self._api("GET", f"/api/filtered_packets?type={PAYLOAD_TYPE_ADVERT}"
                                                   f"&start_timestamp={start:.0f}&end_timestamp={end:.0f}&limit=5000",
                                            timeout=60)
                            rows = res.get("data", []) if isinstance(res, dict) else (res or [])
                            break
                        except Exception as e:
                            log.debug("advert backfill slice failed: %s", e)
                            time.sleep(5)
                    if rows is None:
                        ok = False
                    else:
                        with self.lock:
                            for p in rows:
                                if int(p.get("type", -1)) == PAYLOAD_TYPE_ADVERT:
                                    self.learn_advert(p)
                        total += len(rows)
                    end = start
                    time.sleep(1)
                log.info("Read %d recent adverts from openHop to learn route codes", total)
            finally:
                self._adv_backfill = 2.0 if ok else -time.time()
                self._adv_backfill_busy = False

        threading.Thread(target=work, daemon=True).start()

    def poll_once(self):
        try:
            self.refresh_openhop_info()
            self.refresh_own_identities()
            self.refresh_public_map()
            self.refresh_level_preview()
            self.backfill_adverts()
            self.fetch_noise()
        except Exception:
            pass
        if getattr(self, "retired", False):
            return
        if getattr(self, "standby", None):
            # Another SpamGuard is in charge: read nothing, change nothing, just check often whether
            # it has handed over or stopped.
            if time.time() - self.last_verify > 15:
                self.last_verify = time.time()
                with self.lock:
                    self.sync_policy()
            self.write_runtime()
            return
        packets = self.fetch_packets()
        with self.lock:
            self.ingest(packets)
            if self.decide():
                self.sync_pending = True
            if self.fg_decide():
                self.sync_pending = True
            sig = self.route_sig()
            if sig != self._route_sig:
                # hop sizes in use or shared hop bytes changed: rebuild (only written if the rules differ)
                self._route_sig = sig
                self.sync_pending = True
            self.jam_decide()
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
        self.write_runtime()

    AUTO_MIN_SECONDS = 24 * 3600      # watch at least a day
    AUTO_QUIET_SECONDS = 72 * 3600    # a quiet repeater switches after three days anyway (nothing to lose)
    AUTO_MIN_SPAM = 10                # or as soon as it has seen this much spam it would have stopped
    AUTO_MAX_HELD = 3                 # too many genuine-looking messages held: leave it to you

    def auto_protect_status(self) -> Optional[dict]:
        """Whether SpamGuard will switch itself from Monitor to Protect, when, and what it's waiting for."""
        c = self.cfg
        if c.get("mode") != "monitor" or not c.get("auto_protect", True):
            return None
        now = time.time()
        since = self.monitor_since or self.started
        spam = sum(1 for t in self.catches if t >= since)
        held = sum(1 for h in self.held if h.get("ts", 0) >= since)
        marked = sum(1 for t in self.genuine_marks if t >= since)
        due = since + (self.AUTO_MIN_SECONDS if spam >= self.AUTO_MIN_SPAM else self.AUTO_QUIET_SECONDS)
        waiting = None
        if c.get("paused"):
            waiting = "paused"
        elif marked:
            waiting = "you marked a message it would have blocked as genuine, so it's leaving the switch to you"
        elif held > self.AUTO_MAX_HELD:
            waiting = f"{held} genuine-looking messages were held; check Possibly genuine first"
        return {"since": since, "due": max(due, now) if not waiting else None, "spam": spam, "held": held,
                "waiting": waiting}

    def _maybe_auto_protect(self):
        if time.time() - getattr(self, "_auto_checked", 0) < 300:
            return
        self._auto_checked = time.time()
        s = self.auto_protect_status()
        if not s or s["waiting"] or time.time() < s["due"]:
            return
        with self.lock:
            hours = round((time.time() - s["since"]) / 3600)
            self.settings["mode"] = "protect"
            self.rebuild_cfg()
            self.note(f"Switched to Protect by itself after watching for {hours} hours: it would have stopped "
                      f"{s['spam']} spam message{'' if s['spam'] == 1 else 's'}, and nothing it would block was marked "
                      "as genuine. You can switch back to Monitor at any time on the Overview.")
            self.snapshot_settings("switched to Protect by itself")
            self._save_state(force=True)
            self.sync_policy(force=True)

    def _maybe_guard_frontend(self):
        """As a plugin, SpamGuard's small doorway page shows up in openHop's list of main web pages. It isn't
        a dashboard, so if someone picks it, put openHop's own dashboard back (checked once a minute)."""
        if not IN_PLUGIN or time.time() - getattr(self, "_frontend_checked", 0) < 60:
            return
        self._frontend_checked = time.time()
        try:
            res = self._api("GET", "/api/web_frontends", timeout=10)
            data = res.get("data", res) if isinstance(res, dict) else {}
            if data.get("selected_id") == f"plugin:{PLUGIN_ID}":
                self._api("POST", "/api/update_web_config", {"web": {"web_path": None}}, timeout=15)
                self.note("openHop's main web page had been set to SpamGuard, which would hide openHop's dashboard. "
                          "Put openHop's own dashboard back.")
        except Exception:
            pass

    # ---- moving to the openHop plugin ----
    def _maybe_check_plugins(self):
        """Every 10 minutes, see whether this openHop can run plugins and whether SpamGuard's plugin is
        already installed (normal and Docker installs only)."""
        if IN_PLUGIN or time.time() - getattr(self, "_plugins_checked", 0) < 600:
            return
        self._plugins_checked = time.time()
        try:
            res = self._api("GET", "/api/plugins", timeout=10)
            items = res.get("plugins") or res.get("data") or []
            if isinstance(items, dict):
                items = list(items.values())
            ids = {str(p.get("id")) for p in items if isinstance(p, dict)}
            self.openhop_plugins = {"supported": True, "installed": PLUGIN_ID in ids}
        except urllib.error.HTTPError as e:
            self.openhop_plugins = {"supported": False if e.code == 404 else "down" if e.code == 503 else None,
                                    "installed": False, "error": None if e.code in (404, 503) else f"HTTP {e.code}"}
        except Exception as e:
            # openHop not answering (often just still starting): try again in 30 seconds, not 10 minutes.
            self._plugins_checked = time.time() - 570
            self.openhop_plugins = {"supported": None, "installed": False, "error": str(e)[:80]}

    def move_summary(self) -> dict:
        p = getattr(self, "openhop_plugins", None) or {}
        st = getattr(self, "move_state", None)
        why = None
        if IN_PLUGIN:
            why = "already the plugin"
        elif p.get("supported") is False:
            why = ("This openHop is too old for plugins. Update openHop to 1.1.2 or later (its dashboard's update "
                   "option, or manage.sh upgrade), then come back here.")
        elif p.get("supported") == "down":
            why = ("openHop can run plugins, but its plugin manager isn't running (common after updating openHop). "
                   "On the Pi run: sudo systemctl enable --now openhop-plugin-manager. If that says the service "
                   "doesn't exist, see the plugin guide's \"Plugin manager isn't running\" section.")
        elif p.get("supported") is None:
            why = "Checking whether this openHop can run plugins..." if not p else \
                  ("openHop isn't answering yet, so SpamGuard couldn't check whether it can run plugins. It will try "
                   "again in a moment." if not str(p.get("error") or "").startswith("HTTP") else
                   f"Couldn't check whether this openHop can run plugins ({p.get('error')}).")
        return {"possible": why is None and not (st and st.get("running")), "why_not": why,
                "plugin_installed": bool(p.get("installed")), "state": st}

    def _move_step(self, msg: str, running: bool = True, ok: Optional[bool] = None):
        self.move_state = {"running": running, "message": msg, "ok": ok, "ts": time.time()}
        if ok is not None:
            self.note(("Moved to the openHop plugin: " if ok else "Couldn't move to the openHop plugin: ") + msg)

    def start_move_to_plugin(self) -> dict:
        if (getattr(self, "openhop_plugins", None) or {}).get("supported") is not True:
            self._plugins_checked = 0       # the last check failed or is old news: look again now
            self._maybe_check_plugins()
        s = self.move_summary()
        if not s["possible"]:
            raise ValueError(s["why_not"] or "A move is already under way.")
        if getattr(self, "standby", None):
            raise ValueError("This SpamGuard is waiting while another one looks after the repeater.")
        self._handover_key = os.urandom(16).hex()
        self._handover_until = time.time() + 900
        self._move_step("Getting the plugin for this version...")
        threading.Thread(target=self._move_to_plugin, daemon=True, name="move").start()
        return {"ok": True, "message": "Moving SpamGuard into openHop as a plugin. This takes a minute or two; "
                                       "this page shows how it's going."}

    def _plugin_state(self) -> Optional[str]:
        """openHop's state for SpamGuard's plugin (RUNNING, DISABLED, ...), or None if it isn't installed."""
        try:
            res = self._api("GET", "/api/plugins", timeout=10)
            items = res.get("plugins") or res.get("data") or []
            if isinstance(items, dict):
                items = list(items.values())
            for p in items:
                if isinstance(p, dict) and p.get("id") == PLUGIN_ID:
                    return str(p.get("state") or "")
        except Exception:
            pass
        return None

    def _address_seen_by_openhop(self) -> str:
        """The address openHop (and so the plugin, which runs where openHop runs) can reach this SpamGuard on:
        127.0.0.1 next to a native openHop, or this container's address on the network it shares with openHop."""
        host = urllib.parse.urlparse(self.cfg.get("openhop_url") or "").hostname or "127.0.0.1"
        if host in ("127.0.0.1", "localhost", "::1"):
            return "127.0.0.1"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((socket.gethostbyname(host), 9))
                return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"

    def _plugin_api(self, method: str, path: str, body: Optional[dict] = None, timeout: float = 60) -> dict:
        res = self._api(method, path, body, timeout=timeout)
        return res if isinstance(res, dict) else {}

    def _upload_wheel(self, name: str, data: bytes) -> dict:
        boundary = "----spamguard" + os.urandom(8).hex()
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"wheel\"; filename=\"{name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(self.cfg["openhop_url"].rstrip("/") + "/api/plugins/install", data=body, method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        req.add_header("Accept", "application/json")
        if self.cfg.get("api_key"):
            req.add_header("X-API-Key", self.cfg["api_key"])
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.loads(r.read().decode() or "{}")
        if isinstance(res, dict) and res.get("success") is False:
            raise RuntimeError(res.get("error") or "openHop couldn't install the plugin")
        return res

    def _plugin_runtime(self) -> dict:
        r = self._plugin_api("GET", f"/api/plugins/runtime?id={PLUGIN_ID}", timeout=15)
        for k in ("runtime", "data"):
            if isinstance(r.get(k), dict):
                return r[k]
        return r

    def _move_to_plugin(self):
        try:
            name = f"openhop_spamguard-{plugin_version()}-py3-none-any.whl"
            url = self.cfg.get("plugin_wheel_url") or \
                f"https://github.com/{self._repo()}/releases/download/v{VERSION}/{name}"
            with urllib.request.urlopen(url, timeout=120) as r:
                wheel = r.read()
            self._move_step("Installing the plugin in openHop (it sets up its own copy, which can take a minute)...")
            was_running = self._plugin_state() == "RUNNING"
            started = time.time()
            self._upload_wheel(name, wheel)
            port = int(self.cfg.get("listen_port") or 8091)
            c = self.cfg
            config = {"api_key": c.get("api_key", ""), "openhop_url": c.get("openhop_url"),
                      "mode": c.get("mode", "monitor"), "sensitivity": c.get("sensitivity", "balanced"),
                      "level": c.get("level", 50), "listen_port": port, "hashtag_channels": list(c.get("hashtag_channels") or []),
                      "import_from": f"http://{self._address_seen_by_openhop()}:{port}/handover?key={self._handover_key}"}
            if c.get("listen_api_key"):
                config["listen_api_key"] = c["listen_api_key"]
            self._move_step("Copying the settings across...")
            self._plugin_api("POST", "/api/plugins/settings", {"id": PLUGIN_ID, "config": config, "restart": False})
            self._move_step("Starting the plugin...")
            self._plugin_api("POST", "/api/plugins/enable", {"id": PLUGIN_ID})
            try:
                self._plugin_api("POST", "/api/plugins/start", {"id": PLUGIN_ID})
            except Exception:
                pass  # enabling usually starts it already
            if was_running:  # it was already running (in standby): restart it so it picks up this copy's data
                try:
                    self._plugin_api("POST", "/api/plugins/restart", {"id": PLUGIN_ID}, timeout=30)
                except Exception:
                    pass
            self._move_step("Waiting for the plugin to pick up what this SpamGuard has learnt...")
            plugin_id, deadline = None, time.time() + 300
            while time.time() < deadline:
                try:
                    rt = self._plugin_runtime()
                    # not left over from an older move (plugins before 5.24 don't say when they imported)
                    fresh = "imported_at" not in rt or float(rt.get("imported_at") or 0) >= started - 5
                    if rt.get("imported") and fresh and rt.get("state") == "standby" and rt.get("instance"):
                        plugin_id = rt["instance"]
                        break
                except Exception:
                    pass
                time.sleep(3)
            if not plugin_id:
                raise RuntimeError("the plugin didn't report back within 5 minutes; this SpamGuard carries on as "
                                   "before. Check the plugin's log in openHop (System > Plugins).")
            self._move_step("Handing over...")
            with self.lock:
                self._save_state(force=True)
                res = self._api("GET", "/api/policy")
                pe = dict(res.get("data", res).get("policy_engine") or {})
                objects = dict(pe.get("objects") or {}) if isinstance(pe.get("objects"), dict) else {}
                objects[OWNER_KEY] = self.owner_marker("released", to=plugin_id)
                pe["objects"] = objects
                self._api("POST", "/api/policy", {"policy_engine": pe})
                self.retired = True
            self._handover_key = None
            if install_kind() == "normal":
                folder = os.path.dirname(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])
                req = os.path.join(folder, "update-request")
                if os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"):
                    with open(req + ".tmp", "w") as f:
                        json.dump({"action": "retire", "asked": time.time()}, f)
                    os.replace(req + ".tmp", req)
                    msg = ("Done. The plugin is looking after the repeater now and this copy is switching off. "
                           "Reload this page in a minute: the plugin's page takes over at the same address.")
                else:
                    msg = ("Done. The plugin is looking after the repeater now. Stop this copy: "
                           "sudo systemctl disable --now openhop-spamguard")
            else:
                msg = "Done. The plugin is looking after the repeater now. You can remove this container."
            self._move_step(msg, running=False, ok=True)
        except Exception as e:
            self._handover_key = None
            self._move_step(str(e)[:300], running=False, ok=False)
            log.error("Move to the openHop plugin failed: %s", e)

    def release_on_stop(self):
        """The plugin, stopped cleanly by openHop (disabled or uninstalled), lets go of the repeater at once,
        so a normal install switched back on can take over straight away. A restart takes it back."""
        if getattr(self, "standby", None) or getattr(self, "retired", False):
            return
        try:
            res = self._api("GET", "/api/policy", timeout=2)
            pe = dict(res.get("data", res).get("policy_engine") or {})
            objects = dict(pe.get("objects") or {}) if isinstance(pe.get("objects"), dict) else {}
            if (objects.get(OWNER_KEY) or {}).get("id") == self.instance_id:
                objects[OWNER_KEY] = self.owner_marker("released")
                pe["objects"] = objects
                self._api("POST", "/api/policy", {"policy_engine": pe}, timeout=2)
        except Exception:
            pass

    def handover_state(self, key: str) -> Optional[dict]:
        """The one-time copy of everything learnt, for the plugin taking over (needs the key from the move)."""
        want = getattr(self, "_handover_key", None)
        if not want or time.time() > getattr(self, "_handover_until", 0) or not hmac.compare_digest(str(key), want):
            return None
        with self.lock:
            return self.state_dict()

    def watchdog_loop(self, stop: threading.Event, limit: float = 300):
        """Plugin and Docker installs have no systemd watchdog: if the checking loop ever stalls, exit so
        openHop (or Docker) starts SpamGuard again."""
        while not stop.wait(30):
            last = self.loop_beat or self.started
            if time.time() - last > limit:
                log.error("SpamGuard's checking loop has been stuck for %d s; restarting", time.time() - last)
                self._save_state(force=True)
                os._exit(70)

    @staticmethod
    def _imported_at() -> float:
        try:
            with open(os.path.join(os.environ.get("OPENHOP_PLUGIN_DATA") or ".", "imported.json")) as f:
                return float(json.load(f).get("at") or 0)
        except (OSError, ValueError, TypeError, AttributeError):
            return 0.0

    def write_runtime(self, extra: Optional[dict] = None):
        """As an openHop plugin, keep a short status note openHop's dashboard (and a moving SpamGuard) can read."""
        if not IN_PLUGIN:
            return
        sb = getattr(self, "standby", None)
        note = {"instance": self.instance_id, "version": VERSION, "web_page_port": int(self.cfg.get("listen_port") or 8091),
                "state": "retired" if getattr(self, "retired", False) else "standby" if sb else "active",
                "imported": os.path.exists(os.path.join(os.environ.get("OPENHOP_PLUGIN_DATA") or ".", "imported.json")),
                "imported_at": self._imported_at(),
                "message": (f"Waiting: another SpamGuard ({self.describe_owner(sb)}) is looking after this repeater."
                            if sb else "Protecting this repeater.")}
        if extra:
            note.update(extra)
        if note == getattr(self, "_runtime_note", None):
            return
        self._runtime_note = note
        data = os.environ.get("OPENHOP_PLUGIN_DATA") or os.path.dirname(self.cfg.get("state_file") or ".")
        try:
            tmp = os.path.join(data, "runtime.json.tmp")
            with open(tmp, "w") as f:
                json.dump(note, f)
            os.replace(tmp, os.path.join(data, "runtime.json"))
        except OSError:
            pass

    def run(self, stop: threading.Event):
        threading.Thread(target=self.map_loop, args=(stop,), daemon=True, name="map").start()
        threading.Thread(target=self.live_feed_loop, args=(stop,), daemon=True, name="live").start()
        if install_kind() != "normal":
            threading.Thread(target=self.watchdog_loop, args=(stop,), daemon=True, name="watchdog").start()
        while not stop.is_set():
            t0 = time.time()
            try:
                self._maybe_check_update()
                self._maybe_fix_openhop()
                self._maybe_check_plugins()
                self._maybe_guard_frontend()
                self._maybe_auto_protect()
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
            woke = self.wake.wait(self.cfg["poll_seconds"])
            self.wake.clear()
            if woke and not stop.is_set():
                # let the other copies of a burst arrive, and never check more than about once a second
                stop.wait(max(0.4, 1.0 - (time.time() - t0)))

    # ---- openHop's live packet feed (a nudge to check now; the timed check stays the source of truth) ----
    def _ws_open(self):
        """Open openHop's /ws/packets websocket with the API token. Returns the socket, or raises."""
        u = urllib.parse.urlparse(self.cfg["openhop_url"])
        tls = u.scheme == "https"
        host, port = u.hostname or "127.0.0.1", u.port or (443 if tls else 80)
        sock = socket.create_connection((host, port), timeout=15)
        if tls:
            import ssl
            ctx = ssl.create_default_context()
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2   # refuse anything older than TLS 1.2
            sock = ctx.wrap_socket(sock, server_hostname=host)
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path.rstrip("/") or "") + "/ws/packets"
        req = (f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nX-API-Key: {self.cfg.get('api_key', '')}\r\n\r\n")
        sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(1024)
            if not chunk or len(head) > 16384:
                sock.close()
                raise ConnectionError("no websocket handshake")
            head += chunk
        status = head.split(b"\r\n", 1)[0]
        if b" 101" not in status:
            sock.close()
            raise PermissionError(status.decode(errors="replace")[:60])
        return sock, head.split(b"\r\n\r\n", 1)[1]

    @staticmethod
    def _ws_send(sock, opcode: int, payload: bytes = b""):
        mask = os.urandom(4)
        n = len(payload)
        hdr = bytes([0x80 | opcode]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        sock.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def live_feed_loop(self, stop: threading.Event):
        """Wake the checking loop whenever openHop broadcasts a packet. Any failure just means waiting for
        the normal timed check; it retries quietly with a growing pause."""
        pause = 5
        while not stop.is_set():
            if not self.cfg.get("live_feed", True):
                self.live.update(state="off", since=None)
                stop.wait(30)
                continue
            sock = None
            try:
                sock, buf = self._ws_open()
                sock.settimeout(95)      # openHop pings every 30 s; silence for longer means a dead link
                self.live.update(state="on", since=time.time())
                pause = 5
                frag = b""

                def need(n, sock=sock):
                    nonlocal buf
                    while len(buf) < n:
                        chunk = sock.recv(65536)
                        if not chunk:
                            raise ConnectionError("closed")
                        buf += chunk
                    out, buf = buf[:n], buf[n:]
                    return out

                while not stop.is_set():
                    b0, b1 = need(2)
                    op, n = b0 & 0x0F, b1 & 0x7F
                    if n == 126:
                        n = struct.unpack(">H", need(2))[0]
                    elif n == 127:
                        n = struct.unpack(">Q", need(8))[0]
                    if n > 4 * 1024 * 1024:
                        raise ConnectionError("frame too large")
                    mask = need(4) if b1 & 0x80 else None
                    data = need(n)
                    if mask:
                        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
                    if op == 8:
                        if len(data) >= 2 and struct.unpack(">H", data[:2])[0] == 1008:
                            raise PermissionError("openHop refused the API token for its live feed")
                        raise ConnectionError("closed by openHop")
                    if op == 9:
                        self._ws_send(sock, 10, data)
                        continue
                    if op in (1, 2, 0):
                        frag += data
                        if not b0 & 0x80:
                            continue
                        msg, frag = frag, b""
                        if b'"type": "ping"' in msg[:40] or b'"type":"ping"' in msg[:40]:
                            self._ws_send(sock, 1, b'{"type": "pong"}')
                        elif b'"packet"' in msg[:40]:
                            self.live["packets"] += 1
                            self.wake.set()
            except PermissionError as e:
                # openHop answered but wouldn't upgrade (too old for the feed, or the token was refused)
                self.live.update(state="unavailable", since=None, why=str(e))
                pause = 600
            except Exception as e:
                if self.live.get("state") == "on":
                    log.info("openHop's live packet feed dropped (%s); checking on the timer until it's back", e)
                self.live.update(state="reconnecting", since=None)
            finally:
                if sock:
                    try:
                        sock.close()
                    except OSError:
                        pass
            stop.wait(pause)
            pause = min(pause * 2, 600)

    # ---- health ----
    def send_counts(self, now: float) -> tuple[int, int]:
        """(failed, sent) transmits in the last 15 minutes, as openHop reported them."""
        return (sum(1 for t in self.tx_fails if t > now - 900),
                sum(1 for t in self.tx_oks if t > now - 900))

    def power_status(self, now: float) -> Optional[dict]:
        """The Pi's power, from vcgencmd get_throttled (checked at most once a minute). None when this
        isn't a Raspberry Pi or vcgencmd can't be run."""
        when, res = self._power
        if now - when < 60:
            return res
        res = None
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r"0x([0-9a-fA-F]+)", out)
            if m:
                bits = int(m.group(1), 16)
                res = {"now": bool(bits & 0x1), "throttled_now": bool(bits & 0x4),
                       "since_boot": bool(bits & 0x10000), "throttled_since_boot": bool(bits & 0x40000)}
        except (OSError, subprocess.SubprocessError):
            res = None
        self._power = (now, res)
        return res

    def radio_failing(self, now: float) -> int:
        """How many transmits failed in the last 15 minutes with none succeeding since the first of them
        (0 when the radio looks fine). Three or more in a row means the radio is gone, not a busy channel."""
        fails = [t for t in self.tx_fails if t > now - 900]
        if len(fails) < 3 or (self.tx_ok_at and self.tx_ok_at >= fails[0]):
            return 0
        return len(fails)

    def _note_hash_size(self, p: dict):
        """openHop sends each hop as 1, 2 or 3 bytes (its path.hash.mode). Remember the size the newest
        routed packets use, so the route rules are written at that size."""
        first = parse_path(p.get("original_path"))[:1]
        if first and len(first[0]) in (2, 4, 6):
            self.hash_size = len(first[0]) // 2
            try:
                ts = float(p.get("timestamp") or time.time())
            except (TypeError, ValueError):
                ts = time.time()
            self.hop_sizes[self.hash_size] = max(self.hop_sizes.get(self.hash_size, 0.0), ts)

    HOP_SIZE_WINDOW = 86400          # a hop size counts as in use for a day after it was last seen
    NODE_ID_WINDOW = 14 * 86400      # a repeater heard in an advert counts for two weeks

    def hop_sizes_in_use(self, now: Optional[float] = None) -> list[int]:
        """Hop sizes routed packets used in the last day, plus the newest one. Each sender picks its own
        size, so one mesh can carry 1-byte and 2-byte hops at once; route blocks are written at each."""
        now = time.time() if now is None else now
        sizes = {s for s, t in self.hop_sizes.items() if t > now - self.HOP_SIZE_WINDOW}
        sizes.add(self.hash_size)
        return sorted(sizes)

    def _route_prep(self, now: Optional[float] = None):
        """Before writing route rules: the sizes in use, and how many known repeaters start with each
        1, 2 and 3-byte prefix (from their adverts)."""
        now = time.time() if now is None else now
        self._sizes_now = self.hop_sizes_in_use(now)
        idx: collections.Counter = collections.Counter()
        for k, t in self.node_ids.items():
            if t > now - self.NODE_ID_WINDOW:
                for n in (2, 4, 6):
                    idx[k[:n]] += 1
        self._id_index = idx
        self.hops_narrowed = 0
        self.hops_shared = 0

    def route_sig(self, now: Optional[float] = None) -> tuple:
        """What route rules depend on besides the blocks: the sizes in use and the hop bytes known repeaters use.
        When it changes the rules are rebuilt (openHop's policy is only written if they differ)."""
        now = time.time() if now is None else now
        idx: collections.Counter = collections.Counter()
        for k, t in self.node_ids.items():
            if t > now - self.NODE_ID_WINDOW:
                for n in (2, 4, 6):
                    idx[k[:n]] += 1
        return tuple(self.hop_sizes_in_use(now)), frozenset(idx)

    def _hop_forms(self, value: str) -> tuple[dict[int, str], bool, bool]:
        """A learnt hop at each size in use, as {size: hop}, plus (narrowed, shared).
        A hop learnt longer is shortened, unless another repeater heard in adverts starts with those
        same bytes: the short form would stop that repeater's traffic too, so it is left out (narrowed).
        A hop already at a size that two or more known repeaters share is still written, being the only
        form there is, and reported (shared). Nothing here ever makes a block match more repeaters."""
        idx = getattr(self, "_id_index", None)
        if idx is None:
            idx = collections.Counter()
        sizes = getattr(self, "_sizes_now", None) or [self.hash_size]
        value = (value or "").upper()
        forms: dict[int, str] = {}
        narrowed = shared = False
        for size in sizes:
            n = 2 * size
            if len(value) < n:
                continue
            form = value[:n]
            if len(value) > n:
                if idx[form] - idx[value[:6]] > 0:
                    narrowed = True
                    continue
            elif idx[form] >= 2:
                shared = True
            forms[size] = form
        return forms, narrowed, shared

    def _route_count(self, narrowed: bool, shared: bool, written: bool):
        if narrowed:
            self.hops_narrowed += 1
        if shared:
            self.hops_shared += 1
        if not written and not narrowed:
            self.hops_stale += 1

    def _size_id(self, b: dict, key: str) -> int:
        sids = b.setdefault("size_ids", {})
        if key not in sids:
            sids[key] = self._new_id()
        return sids[key]

    @staticmethod
    def _same_hop(a: str, b: str) -> bool:
        """Two hops match when they agree on the bytes both have (a 2-byte hop starts with its 1-byte form)."""
        m = min(len(a or ""), len(b or ""))
        return m > 0 and a[:m] == b[:m]

    def health(self) -> dict:
        now = time.time()
        c = self.cfg
        sysr = system_readings(c.get("evidence_dir", "/var/lib/openhop_spamguard"))
        restarts = systemd_value("openhop-spamguard", "NRestarts")
        # systemd says "inactive" for a service it has never heard of, so only believe it when openHop's service
        # really is installed on this machine (openHop may run in Docker or on another computer).
        openhop_state = (systemd_value("openhop-repeater", "ActiveState")
                         if systemd_value("openhop-repeater", "LoadState") == "loaded" else None)
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
        jam = self.jam if self.cfg.get("interference_watch", True) else {}
        if jam.get("since") and jam.get("baseline") is not None and jam.get("current") is not None:
            rise = jam["current"] - jam["baseline"]
            warnings.append(f"Interference on the radio channel for {self.fmt_secs(now - float(jam['since']))}: the noise is "
                            f"{rise:.0f} dB above this site's normal, so the repeater hears only about {self.range_share(rise)}% "
                            "as far as usual. The FloodGuard page has the details.")
        commands: dict[int, str] = {}   # warning number -> a command to show with a Copy button
        rfix = self.openhop_rulecheck_fix()
        if rfix is False:
            cmd = fix_command("rule")
            lead = ("Recommended: openHop has a known bug (reported to openHop) that occasionally lets blocked spam "
                    "through, or drops a genuine message. "
                    + (f"openHop {OPENHOP_FIXED_IN} and later fix this, so updating openHop is the best cure. "
                       if OPENHOP_FIXED_IN else ""))
            if cmd:
                commands[len(warnings)] = cmd
                warnings.append(lead + "Running this one command on the Pi (or whichever computer runs openHop) fixes it. "
                                "It changes one line, keeps a backup, and can be undone with --undo.")
            elif install_kind() == "normal":
                warnings.append(lead + "Press Apply openHop fix below. It changes one line, keeps a backup, and can be undone.")
            else:
                warnings.append(lead + "openHop runs in a container here, so the fix can't be applied from outside it; "
                                "it goes away once openHop releases its own fix.")
        fix = self.openhop_speed_fix()
        hint = fix_hint("speed")
        if fix is False and hint and lag is not None and lag >= c.get("lag_warn_seconds", 30):
            # Only worth doing when openHop is actually falling behind; most repeaters keep up without it.
            cmd = fix_command("speed")
            if cmd:
                commands[len(warnings)] = cmd
                warnings.append("openHop's speed fix isn't in place, and it would help openHop keep up. Run this on the "
                                "Pi (or whichever computer runs openHop); it keeps a backup and can be undone.")
            else:
                warnings.append("openHop's speed fix isn't in place (an openHop upgrade puts the old setting back), and it "
                                f"would help openHop keep up. To apply it, {hint}")
        quiet = c.get("quiet_warn_minutes", 20) * 60
        if self.heard_at and self.last_error is None and now - self.heard_at > quiet and now - self.started > quiet:
            warnings.append(f"openHop hasn't reported any new packets for {round((now - self.heard_at) / 60)} minutes. "
                            "If its own packet list has stopped too, its radio may have stopped receiving: "
                            + ("restart openHop's container." if IN_DOCKER else
                               "restart openHop (sudo systemctl restart openhop-repeater)."))
        radio = self.radio_failing(now)
        if radio:
            problems.append(f"openHop's radio isn't transmitting: {radio} sends failed in the last 15 minutes and none "
                            "got out. Messages from your own companion won't leave the repeater, and nothing is "
                            "being repeated. If the radio is a USB board, it has probably dropped off the Pi: check "
                            "the cable and the power supply (a weak supply often makes USB radios disconnect), then "
                            + ("restart openHop's container." if IN_DOCKER else
                               "restart openHop (sudo systemctl restart openhop-repeater)."))
        power = self.power_status(now)
        if power and power["now"]:
            warnings.append("The Pi's power is too low right now (under-voltage). That makes USB devices drop off and "
                            "transmits fail, so check the power supply first: use the official 5.1 V 3 A supply, "
                            "a short good-quality USB cable, or a powered USB hub for the radio and any SDR dongle.")
        elif power and power["since_boot"]:
            warnings.append("The Pi's power dipped too low at some point since it booted. Radio drop-outs and failed "
                            "transmits can come from that, so check the power supply if they keep happening.")
        failed, sent = self.send_counts(now)
        if not radio and failed >= 3 and failed * 5 >= failed + sent:
            warnings.append(f"{failed} of {failed + sent} transmits failed in the last 15 minutes, though some got out. "
                            "Messages from your companion and some relayed packets are being lost. Check the Pi's power "
                            "and the radio's USB cable, and see if the radio is busy with interference.")
        if self.hops_stale:
            in_use = " and ".join(f"{z}-byte" for z in self.hop_sizes_in_use())
            warnings.append(f"{self.hops_stale} route block(s) were learnt from shorter hops than the mesh is using now "
                            f"({in_use} hops). They stay off until that route is seen again at a size in use.")
        if self.hops_narrowed:
            warnings.append(f"{self.hops_narrowed} route block(s) were not written in their shorter form, because another "
                            "repeater this one has heard starts with the same bytes and would have been blocked too. "
                            "They still apply to the longer hops they were learnt from.")
        if self.hops_shared:
            warnings.append(f"{self.hops_shared} route block(s) are on a 1-byte hop that more than one repeater heard here "
                            "uses, so they may also stop traffic through those other repeaters. Blocks learnt from "
                            "2-byte hops don't have this problem.")
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
        if not watchdog and restarts is not None and install_kind() == "normal":
            warnings.append("Automatic restart-on-hang is not active. Re-run the installer to enable it.")
        state = "bad" if problems else ("warn" if warnings else "ok")
        return {"state": state, "problems": problems, "warnings": warnings,
                "commands": [commands.get(i) for i in range(len(warnings))],
                "uptime": round(now - self.started), "restarts": int(restarts) if (restarts or "").isdigit() else None,
                "watchdog": watchdog, "last_check": self.loop_beat, "checks": self.loop_count,
                "check_ms": self.poll_ms, "openhop_ms": self.openhop_ms, "openhop_service": openhop_state,
                "openhop_ok": self.last_error is None and self.last_poll_ok is not None,
                "rules_expected": self.rules_expected, "rules_seen": self.rules_seen, "self_heals": self.self_heals,
                "live_feed": self.live.get("state"), "live_packets": self.live.get("packets", 0),
                "errors_hour": errors_hour, "last_error": self.last_error,
                "last_heard": self.last_packet_ts, "openhop_lag_s": None if lag is None else round(lag),
                "openhop_speed_fix": fix, "openhop_rulecheck_fix": rfix, "openhop_fixed_in": OPENHOP_FIXED_IN,
                "kind": install_kind(),
                "can_apply_fix": install_kind() == "normal"
                and os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"), **sysr}

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

    # ---- progress shown while an update installs ----
    # Stage words in the installer's output, and how far through the update each one means (a guide, not
    # a measurement: openHop doesn't say how many steps there will be).
    UPDATE_STAGES = (("collecting", 38), ("downloading", 46), ("building wheel", 55),
                     ("installing collected packages", 72), ("successfully installed", 86))

    @staticmethod
    def clean_output_line(raw: Any) -> str:
        """One line of installer output made safe to show: no escape codes or control characters."""
        t = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", str(raw or ""))
        t = re.sub(r"[\x00-\x1f\x7f]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()[:140]

    def _update_step(self, message: Optional[str] = None, pct: Optional[float] = None,
                     line: Optional[str] = None, state: str = "running"):
        """Record how far the update has got. The percentage only ever goes up; the last two lines of the
        installer's output are kept."""
        cur = dict(getattr(self, "plugin_update", None) or {})
        lines = list(cur.get("lines") or [])
        line = self.clean_output_line(line) if line else ""
        if line:
            lines = (lines + [line])[-2:]
        done = int(cur.get("pct") or 0)
        if pct is not None:
            done = max(done, int(pct))
        self.plugin_update = {"state": state, "ts": time.time(),
                              "message": cur.get("message", "") if message is None else message,
                              "pct": min(done, 99 if state == "running" else 100), "lines": lines}

    def _on_install_line(self, raw: Any):
        line = self.clean_output_line(raw)
        if not line:
            return
        self._install_lines = getattr(self, "_install_lines", 0) + 1
        low = line.lower()
        pct = min(36 + self._install_lines // 3, 70)       # creeps up while pip works through its steps
        for word, at in self.UPDATE_STAGES:
            if word in low:
                pct = max(pct, at)
        self._update_step(pct=pct, line=line)

    def _follow_install_progress(self, stop: threading.Event):
        """Read openHop's live feed of the plugin install (its /api/plugins/progress stream) and keep the
        last lines of it. Reconnects until the upload has finished; it never changes anything in openHop."""
        seen, fresh = 0, "&fresh=1"
        while not stop.is_set():
            try:
                req = urllib.request.Request(
                    self.cfg["openhop_url"].rstrip("/") + f"/api/plugins/progress?id={PLUGIN_ID}&since={seen}{fresh}")
                if self.cfg.get("api_key"):
                    req.add_header("X-API-Key", self.cfg["api_key"])
                with urllib.request.urlopen(req, timeout=20) as r:
                    for raw in r:
                        if stop.is_set():
                            return
                        raw = raw.decode("utf-8", "replace").strip()
                        if not raw.startswith("data:"):
                            continue
                        ev = json.loads(raw[5:])
                        if ev.get("type") == "line":
                            seen += 1
                            self._on_install_line(ev.get("line"))
                        elif ev.get("type") == "done" and ev.get("state") in ("complete", "error"):
                            return
            except Exception as e:
                log.debug("install progress feed: %s", e)
            fresh = ""
            stop.wait(1.0)

    PREFLIGHT_NETWORK = ("retrying", "could not fetch url", "failed to establish", "connection", "temporary failure",
                         "name or service not known", "timed out", "ssl", "proxy")

    def plugin_preflight(self, wheel: bytes) -> Optional[str]:
        """Before openHop removes the running version: will the new version's libraries install from ready-made
        builds on this machine? When the newest version of one only comes as source code, openHop would compile
        it, which on a small Pi can take longer than openHop waits and leave SpamGuard uninstalled. Returns a
        plain-language reason, or None when all is well or it can't tell (no network, no pip), so only a clear
        answer ever stops an update."""
        import zipfile
        import tempfile
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(wheel)) as z:
                meta = next((n for n in z.namelist() if n.endswith(".dist-info/METADATA")), None)
                text = z.read(meta).decode("utf-8", "replace") if meta else ""
        except Exception:
            return None
        reqs = [m.group(1).strip() for m in re.finditer(r"(?m)^Requires-Dist:\s*([^;\r\n]+?)\s*$", text)]
        if not reqs:
            return None
        names = ", ".join(sorted({re.split(r"[<>=!~ \[]", q, maxsplit=1)[0] for q in reqs}))
        # Ask pip for exactly what openHop's install would fetch: the newest version of each library. A new
        # release often comes out as source code first, with ready-made builds for small machines following
        # a day or so later; only the newest version counts, since that is the one openHop would compile.
        tmp = tempfile.mkdtemp(prefix="spamguard-preflight-")
        try:
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps",
                                    "--disable-pip-version-check", "--retries", "1", "--timeout", "15", "-d", tmp, *reqs],
                                   capture_output=True, text=True, timeout=300)
            except (subprocess.TimeoutExpired, OSError):
                return None
            got = os.listdir(tmp) if os.path.isdir(tmp) else []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        out = ((r.stdout or "") + (r.stderr or "")).lower()
        if r.returncode != 0:
            if any(w in out for w in self.PREFLIGHT_NETWORK) or "no matching distribution" not in out:
                return None
            return ("Update stopped before anything was changed. This machine can't get one of SpamGuard's "
                    f"libraries ({names}), so openHop couldn't install the new version. Press Update anyway if "
                    "you'd rather try, or install the plugin file from openHop's Plugins page.")
        source = sorted({re.split(r"-\d", f, maxsplit=1)[0] for f in got if not f.endswith(".whl")})
        if not source:
            return None
        return ("Update stopped before anything was changed. A new version of " + ", ".join(source) + " (one of "
                "SpamGuard's libraries) has come out without a ready-made build for this machine yet, so openHop "
                "would have to compile it. On a small Pi that can take longer than openHop waits and leave "
                "SpamGuard uninstalled. Ready-made builds usually follow within a day, so try again tomorrow, or "
                "press Update anyway if you'd rather wait for the compile.")

    def start_plugin_update(self, want: str, force: bool = False) -> dict:
        """As an openHop plugin: fetch the new version's plugin file, hand it to openHop, and ask openHop to
        restart SpamGuard on it. Settings and everything learnt stay in the plugin's data folder."""
        if (getattr(self, "plugin_update", None) or {}).get("state") == "running":
            return {"ok": True, "message": "Already updating."}
        self._install_lines = 0
        self.plugin_update = {"state": "running", "message": f"Getting version {want}...", "ts": time.time(),
                              "pct": 2, "lines": []}

        def work():
            stop = threading.Event()
            try:
                name = f"openhop_spamguard-{plugin_version(want)}-py3-none-any.whl"
                url = (self.cfg.get("plugin_wheel_url") or
                       f"https://github.com/{self._repo()}/releases/download/v{{version}}/{{name}}")
                with urllib.request.urlopen(url.format(version=want, name=name), timeout=120) as r:
                    total = int(r.headers.get("Content-Length") or 0)
                    buf = bytearray()
                    while True:
                        chunk = r.read(65536)
                        if not chunk:
                            break
                        buf += chunk
                        if total:
                            self._update_step(pct=3 + 30 * len(buf) / total)
                    wheel = bytes(buf)
                if not force and self.cfg.get("plugin_preflight", True):
                    self._update_step("Checking the update can install on this machine...", pct=34)
                    why = self.plugin_preflight(wheel)
                    if why:
                        self._update_step(why, state="failed")
                        self.plugin_update["can_force"] = True
                        log.warning("Plugin update to %s not started: %s", want, why)
                        return
                self._update_step("openHop is installing the new version (this can take a minute)...", pct=35)
                threading.Thread(target=self._follow_install_progress, args=(stop,), daemon=True,
                                 name="install-progress").start()
                try:
                    self._upload_wheel(name, wheel)
                finally:
                    stop.set()
                self._update_step(f"Restarting on version {want}; this page reconnects by itself.", pct=90)
                self._save_state(force=True)
                self._plugin_api("POST", "/api/plugins/restart", {"id": PLUGIN_ID}, timeout=30)
            except Exception as e:
                stop.set()
                # A restart that cut our own request short is the update working, not failing.
                if not isinstance(e, (ConnectionError, TimeoutError, socket.timeout, urllib.error.URLError)) \
                        or self.plugin_update.get("message", "").startswith("Getting"):
                    self._update_step(f"Update failed: {str(e)[:200]}", state="failed")
                    log.error("Plugin update failed: %s", e)
        threading.Thread(target=work, daemon=True, name="plugin-update").start()
        self.note(f"Update to v{want} requested from the web page")
        return {"ok": True, "message": f"Updating to v{want}. SpamGuard restarts in a minute or two; this page reconnects by itself."}

    def update_status(self) -> dict:
        if IN_PLUGIN:
            return dict(getattr(self, "plugin_update", None) or {})
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
                "installer_ready": IN_PLUGIN or os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"),
                "docker": IN_DOCKER, "docker_update": DOCKER_UPDATE, "plugin": IN_PLUGIN,
                "managed_update": managed_update(),
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
        if managed_update():
            raise ValueError(managed_update())
        if IN_PLUGIN:
            return self.start_plugin_update(want, force=bool(body.get("force")))
        if not os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"):
            raise ValueError("The updater isn't set up on this Pi yet. Run the installer once by hand: sudo bash install.sh")
        folder = os.path.dirname(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])
        tmp = os.path.join(folder, "update-request.tmp")
        with open(tmp, "w") as f:
            json.dump({"version": "v" + want, "asked": time.time()}, f)
        os.replace(tmp, os.path.join(folder, "update-request"))
        self.note(f"Update to v{want} requested from the web page")
        return {"ok": True, "message": f"Updating to v{want}. SpamGuard restarts in a minute or two; this page reconnects by itself."}

    def request_openhop_fix(self, why: str = "") -> dict:
        """Ask the root-owned updater to (re-)apply the openHop rule-check fix."""
        if install_kind() != "normal":
            hint = fix_hint("rule")
            raise ValueError(("To apply it, " + hint) if hint else
                             "openHop runs in a container here, so this fix can't be applied from outside it.")
        if not os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"):
            raise ValueError("The updater isn't set up on this Pi yet. Run: sudo bash /opt/openhop_spamguard/tune-openhop.sh")
        folder = os.path.dirname(self.cfg.get("state_file") or DEFAULT_CONFIG["state_file"])
        req = os.path.join(folder, "update-request")
        if os.path.exists(req):
            return {"ok": True, "message": "Already in progress."}
        tmp = req + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"action": "openhop-fix", "asked": time.time()}, f)
        os.replace(tmp, req)
        self._fix_requested = time.time()
        self._rfix_cache = None
        self.note("Applying the openHop rule-check fix" + (f" ({why})" if why else "") + "; openHop restarts for a few seconds")
        return {"ok": True, "message": "Applying the openHop fix. openHop restarts for a few seconds."}

    def _maybe_fix_openhop(self):
        """If an openHop update has removed the rule-check fix, put it back (once an hour at most)."""
        if not self.cfg.get("openhop_autofix", True) or install_kind() != "normal":
            return
        if time.time() - getattr(self, "_fix_requested", 0) < 3600 or time.time() - self.started < 120:
            return
        if self.openhop_rulecheck_fix() is False and os.path.exists("/etc/systemd/system/openhop-spamguard-update.path"):
            try:
                self.request_openhop_fix("openHop no longer had it, probably after an openHop update")
            except Exception as e:
                log.info("Could not request the openHop fix: %s", e)
                self._fix_requested = time.time()

    def openhop_rulecheck_fix(self) -> Optional[bool]:
        """True if openHop's rule checker is safe (patched by tune-openhop.sh, or fixed upstream),
        False if it has the id()-keyed decrypt cache that can let blocked spam through, None if unknown."""
        now = time.time()
        cached = getattr(self, "_rfix_cache", None)
        if cached and now - cached[0] < 300:
            return cached[1]
        result = None
        try:
            for path in glob.glob(self.cfg.get("openhop_dir", "/opt/openhop_repeater") + "/**/repeater/policy_engine.py",
                                  recursive=True)[:1]:
                with open(path, encoding="utf-8", errors="replace") as f:
                    src = f.read()
                if "spamguard-fix: clear decrypt cache" in src:
                    result = True
                elif "packet_key = id(packet)" in src and "_channel_decrypt_cache[packet_key]" in src:
                    m = re.search(r"def evaluate\(.*?for rule in self\.rules", src, re.S)
                    result = bool(m and "_channel_decrypt_cache.clear()" in m.group(0))
                else:
                    result = True
        except Exception:
            result = None
        self._rfix_cache = (now, result)
        return result

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
            for _cid, cc in sorted(a["campaigns"].items(), key=lambda kv: -len(kv[1]["senders"])):
                campaigns.append({"senders": len(cc["senders"]), "count": len(cc["events"]),
                                  "example": cc["events"][-1].text[:120],
                                  "variants": len({e.text for e in cc["events"]}),
                                  "hops": dict(cc["hops"].most_common(6))})
            recent = []
            shown_from = max(getattr(self, "reset_at", 0), self.view_marks.get("recent", 0))
            for e in [e for e in list(a["long"])[-80:][::-1] if e.ts >= shown_from]:
                recent.append({"ts": e.ts, "time": time.strftime("%H:%M:%S", time.localtime(e.ts)),
                               "path": ">".join(e.path) or "direct", "first_hop": e.first_hop,
                               "sender": e.sender, "text": e.text[:160], "channel": e.channel,
                               "random": e.random, "name_score": e.name_score, "obfuscated": e.obfuscated, "garbage": e.garbage,
                               "trusted": e.sender in self.allow_senders, "known": self.is_known(e.sender),
                               "campaign": e.campaign is not None,
                               "matched": e.matched, "packet": e.packet,
                               "label": self.labels.get(e.packet or "") or self.labels.get(f"{e.sender}|{e.text}"),
                               "matched_desc": self.describe(self.blocks[e.matched]) if e.matched in self.blocks else None})
            blocks = []
            rank = {"lockdown": -1, "manual": 0, "hop": 1, "rotation": 1, "route-auto": 1, "hop-route": 1, "links": 1, "campaign": 2, "dedupe": 3}
            for k, b in sorted(self.blocks.items(), key=lambda kv: (rank.get(kv[1].get("source"), 2), -kv[1].get("hits", 0))):
                blocks.append({"key": k, "kind": b["kind"], "value": b["value"], "source": b.get("source"),
                               "reason": b.get("reason"), "hits": b.get("hits", 0), "last_hit": b.get("last_hit"),
                               "created": b["created"], "expires_in": round(b["expires"] - now),
                               "permanent": b["expires"] - now > PERMANENT_SECONDS / 2,
                               "action": b.get("action"), "effective": "paused" if c.get("paused") else self.rule_action(b),
                               "match": b.get("match"), "mode": self.hop_mode(b) if b["kind"] == "hop" else None,
                               "sender": b.get("sender"), "who": b.get("who"), "after": b.get("after"),
                               "only_channel": b.get("only_channel"),
                               "rules": self.rule_numbers(b),
                               "paths": sorted(b.get("paths") or {}) if b["kind"] == "hop" else None,
                               "allowed": sorted(self.allowed_origins(b)) if b["kind"] == "suffix" else None,
                               "user_allowed": b.get("user_allowed") if b["kind"] == "suffix" else None,
                               "unknown_seen": sorted({e.first_hop for e in a["window"] if b["kind"] == "suffix"
                                                       and e.path and tuple(e.path[1:]) == tuple(b["value"])
                                                       and e.first_hop not in self.allowed_origins(b)}) if b["kind"] == "suffix" else None,
                               "describe": self.describe(b)})
            since = max(now - 86400, getattr(self, "reset_at", 0))   # the page starts at a reset
            shown = [t for t in self.catches if t >= since]
            caught_24h = len(shown)
            by_hour = [0] * 24  # index 23 = the most recent hour
            for t in shown:
                age = int((now - t) // 3600)
                if 0 <= age < 24:
                    by_hour[23 - age] += 1
            last_catch = max(shown) if shown else None
            settings = {m["key"]: c.get(m["key"]) for m in SETTINGS_META}
            return {
                "version": VERSION, "floodguard_version": FLOODGUARD_VERSION,
                "mode": c["mode"], "paused": bool(c.get("paused")), "sensitivity": c["sensitivity"],
                "level": {"value": c.get("level", 50), "name": level_name(c.get("level", 50)),
                          "names": LEVEL_NAMES, "own": self.own_level_values(), "mine": self.my_level_values(),
                          "preview": self.preview_summary()},
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
                "settings": settings, "meta": [m for m in SETTINGS_META if m["key"] not in hidden_settings()],
                "presets": PRESETS,
                "overridden": sorted(k for k in self.settings if k in META_BY_KEY),
                "channels": sorted(c["channels"]),
                "rule_summary": getattr(self, "rule_summary", None),
                "profiles": {"list": [dict(v, name=k) for k, v in sorted(self.profiles.items())],
                             "in_use": self.profile_in_use, "modified": self.profile_modified(),
                             "current": self.current_profile(), "keys": profile_keys()},
                "channel_choices": sorted(n for n, k in self.openhop_channels.items()
                                          if n not in c["channels"] and k not in set(c["channels"].values())),
                "route_suggestions": [{"key": k, "route": ">".join(v["route"]), "names": v["names"],
                                       "messages": v["messages"], "minutes": ROUTE_SURGE_SECONDS // 60,
                                       "ttl": int(c.get("route_surge_ttl", 7200))}
                                      for k, v in sorted(self.route_suggest.items(), key=lambda kv: -kv[1]["names"])],
                "blocks": blocks, "hops": hops[:40], "campaigns": campaigns[:15], "recent": recent,
                "evidence": dict(self.evidence.summary(), enabled=True) if self.evidence else
                            {"enabled": False, **EvidenceLog(c["evidence_dir"]).summary()},
                "own": self.own_summary(),
                "known": {"count": len(self.known_list()), "min_msgs": int(c.get("known_min_msgs", 1)),
                          "learning": sum(1 for k in self.known if not self.is_known(k)),
                          # who gets let through blocks, most recently heard first (names only, no messages)
                          "people": [{"name": k, "msgs": v[2], "first": v[0], "last": v[1],
                                      "known": self.is_known(k), "trusted": k in self.allow_senders}
                                     for k, v in sorted(self.known.items(), key=lambda kv: -kv[1][1])[:1000]]
                                    + [{"name": n, "msgs": 0, "first": None, "last": None, "known": True, "trusted": True}
                                       for n in sorted(self.allow_senders) if n and n not in self.known]},
                "metrics": self.metrics(),
                "held": [dict(h, time=time.strftime("%H:%M", time.localtime(h["ts"])))
                         for h in reversed(self.held)
                         if h["ts"] > max(since, self.view_marks.get("held", 0)) and h["sender"] not in self.allow_senders and not self.is_known(h["sender"])][:20],
                "lockdown": ({"left": round(self.blocks["lockdown"]["expires"] - now)} if "lockdown" in self.blocks else None),
                "learnt": {"routes": len(self.routes), "relays": len(self.relays),
                           "origins": len({k.split(">", 1)[0] for k, v in self.routes.items() if v[2] > 0})},
                "allow": {"hops": sorted(self.allow_hops), "senders": sorted(self.allow_senders),
                          "texts": sorted(self.allow_texts)},
                "suppressed": {k: round(v - now) for k, v in self.suppressed.items()},
                "activity": [{"ts": x["ts"], "msg": x["msg"]} for x in list(self.activity)[:80]
                             if x["ts"] >= getattr(self, "reset_at", 0)],
                "reset_at": getattr(self, "reset_at", 0) or None,
                "auto_protect": self.auto_protect_status(),
                "window_seconds": c["window_seconds"],
                "update": self.update_summary(),
                "install": {"kind": install_kind(), "instance": self.instance_id,
                            "standby": ({"who": self.describe_owner(self.standby), "since": self.standby.get("ts")}
                                        if getattr(self, "standby", None) else None),
                            "retired": bool(getattr(self, "retired", False)),
                            "move": self.move_summary()},
            }

    # ---- actions from the web page ----
    # ---- settings profiles ----
    def current_profile(self) -> dict:
        """The detection settings in force now, as a profile: the sensitivity plus every value you changed."""
        return {"sensitivity": self.cfg.get("sensitivity", "balanced"), "level": self.cfg.get("level", 50),
                "values": {k: self.settings[k] for k in profile_keys() if k in self.settings}}

    @staticmethod
    def check_profile(p) -> dict:
        """A profile from a file or the page, checked: only known detection settings, within their limits.
        Anything else (channels, keys, exceptions, the mode, unknown fields) is refused, not ignored."""
        if not isinstance(p, dict):
            raise ValueError("That isn't a SpamGuard profile")
        extra = set(p) - {"format", "version", "name", "sensitivity", "level", "values", "saved"}
        if extra:
            raise ValueError("A profile can't hold " + ", ".join(sorted(extra)))
        if p.get("format", PROFILE_FORMAT) != PROFILE_FORMAT or int(p.get("version", 1)) != 1:
            raise ValueError("That isn't a SpamGuard profile (or it is from a newer version)")
        sens = p.get("sensitivity", "balanced")
        if sens not in PRESETS:
            raise ValueError("Unknown sensitivity in the profile")
        vals = p.get("values") or {}
        if not isinstance(vals, dict):
            raise ValueError("The profile's values aren't readable")
        allowed = set(profile_keys())
        bad = [k for k in vals if k not in allowed]
        if bad:
            raise ValueError("A profile can only hold detection settings, not " + ", ".join(sorted(bad)[:5]))
        out = {}
        for k, v in vals.items():
            m = META_BY_KEY[k]
            if m["type"] == "bool":
                v = bool(v)
            elif m["type"] == "int":
                v = int(v)
                if not m.get("min", v) <= v <= m.get("max", v):
                    raise ValueError(f"'{m['label']}' in the profile must be between {m['min']} and {m['max']}")
            elif m["type"] == "choice":
                if v not in [x[0] for x in m["choices"]]:
                    raise ValueError(f"Invalid choice for '{m['label']}' in the profile")
            elif m["type"] == "list":
                v = [str(x) for x in (v if isinstance(v, list) else [])][:50]
                for x in v:
                    re.compile(x)
            out[k] = v
        level = p.get("level", SENSITIVITY_LEVEL[sens])
        try:
            level = int(level)
        except (TypeError, ValueError):
            raise ValueError("The protection level in the profile isn't a number") from None
        if not 0 <= level <= 100:
            raise ValueError("The protection level in the profile must be from 0 to 100")
        return {"sensitivity": level_sensitivity(level), "level": level, "values": out}

    def profile_modified(self) -> bool:
        p = self.profiles.get(self.profile_in_use or "")
        if not p:
            return False
        cur = self.current_profile()
        level = p.get("level", SENSITIVITY_LEVEL.get(p.get("sensitivity"), 50))
        return cur["level"] != level or cur["values"] != (p.get("values") or {})

    def apply_profile(self, p: dict):
        """Put a profile's detection settings in place. Everything a profile doesn't hold stays as it is."""
        p = self.check_profile(p)
        with self.lock:
            for k in profile_keys():
                self.settings.pop(k, None)
        self.apply_settings({"level": p["level"]})
        if p["values"]:
            self.apply_settings(dict(p["values"]))

    def apply_settings(self, body: dict) -> dict:
        with self.lock:
            if body.get("reset"):
                self.settings = {k: v for k, v in self.settings.items() if k in EXTRA_TUNABLES or k in KEEP_ON_RESET}
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
                        # The older choice: the same as that level, and it replaces your own values.
                        for m in SETTINGS_META:
                            if m.get("preset"):
                                self.settings.pop(m["key"], None)
                        k, v = "level", SENSITIVITY_LEVEL[v]
                        self.settings.pop("sensitivity", None)
                    elif k == "level":
                        try:
                            v = int(v)
                        except (TypeError, ValueError):
                            raise ValueError("The protection level must be a number from 0 to 100") from None
                        if not 0 <= v <= 100:
                            raise ValueError("The protection level must be a number from 0 to 100")
                        self.settings.pop("sensitivity", None)
                    elif k == "replace_own":
                        # With a new level: drop your own values for the settings the level sets.
                        if v:
                            for m in SETTINGS_META:
                                if m.get("preset"):
                                    self.settings.pop(m["key"], None)
                        continue
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
                                    raise ValueError(f"pattern '{p}' is not valid: {err}") from None
                    else:
                        raise ValueError(f"unknown setting {k}")
                    new[k] = v
                if new.get("mode") == "monitor" and self.cfg.get("mode") == "protect":
                    new["auto_protect"] = False   # you chose Monitor on purpose: don't switch back by yourself
                if new.get("mode") == "monitor" or (new.get("mode") is None and "auto_protect" in new and new["auto_protect"]):
                    self.monitor_since = time.time() if new.get("mode") == "monitor" else (self.monitor_since or time.time())
                self.settings.update(new)
                words = {"mode": {"monitor": "Monitor only", "protect": "Protect"},
                         "paused": {True: "Paused", False: "Resumed"}}
                if "level" in new:
                    words["level"] = {new["level"]: f"Protection level {new['level']} ({level_name(new['level'])})"}
                if new:
                    self.note("Changed: " + ", ".join(
                        (words.get(k, {}).get(v) if not isinstance(v, (list, dict)) else None)
                        or f"{META_BY_KEY[k]['label'] if k in META_BY_KEY else k} = {', '.join(map(str, v)) if isinstance(v, list) else v}"
                        for k, v in new.items()))
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
                if b and b.get("source") == "dedupe":
                    self.release_duplicate(b)
                    msg = "Duplicate block removed. The copies so far are forgiven; if the message keeps being copied, the next copy starts a new block."
                else:
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
                only = body.get("channel") if body.get("channel") in self.cfg["channels"] else None
                self._add_block(key, "hop", hop, "Added by you", "manual",
                                ttl=int(body.get("ttl_seconds") or self.cfg["block_ttl_seconds"]),
                                match=(body.get("match") if body.get("match") in ("exact_paths", "contains", "contains_known") else None),
                                extra={"only_channel": only} if only else None)
                self.learn_paths(list(self.events))
                if self.hop_mode(self.blocks[key]) == "exact_paths" and not self.blocks[key]["paths"]:
                    msg = f"Blocking repeater {hop}. Routes will be learnt as its messages arrive."
            elif op == "block_route":
                hops = parse_route(body.get("route", ""))
                key = "route:" + ">".join(hops)
                self.suppressed.pop(key, None)
                self.blocks.pop(key, None)
                only = body.get("channel") if body.get("channel") in self.cfg["channels"] else None
                self._add_block(key, "route", hops, "Added by you", "manual",
                                ttl=int(body.get("ttl_seconds") or self.cfg["block_ttl_seconds"]),
                                extra={"only_channel": only} if only else None)
                msg = (f"Blocking messages that start on route {'>'.join(hops)}. People SpamGuard knows still get through."
                       + (" Monitor mode: nothing is actually blocked." if self.cfg["mode"] != "protect" else ""))
            elif op in ("accept_route", "dismiss_route"):
                hops = parse_route(body.get("route", ""))
                key = "route:" + ">".join(hops)
                self.route_suggest.pop(key, None)
                if op == "dismiss_route":
                    self.suppressed[key] = time.time() + 86400
                    msg = f"Won't suggest route {'>'.join(hops)} again for a day."
                else:
                    self.suppressed.pop(key, None)
                    self._add_block(key, "route", hops, "Accepted from SpamGuard's suggestion", "manual",
                                    ttl=int(self.cfg.get("route_surge_ttl", 7200)))
                    msg = (f"Blocking messages that start on route {'>'.join(hops)} for {self.fmt_secs(int(self.cfg.get('route_surge_ttl', 7200)))}. People SpamGuard knows still get through."
                           + (" Monitor mode: nothing is actually blocked." if self.cfg["mode"] != "protect" else ""))
            elif op in ("block_text", "mark_spam"):
                if op == "mark_spam":
                    self.ev({"type": "label", "label": "spam", "sender": body.get("sender"), "text": body.get("text"),
                             "path": body.get("path"), "packet": body.get("packet")})
                text = str(body.get("text", "")).strip()
                if op == "mark_spam":
                    text = middle_chunk(text, self.cfg["text_rule_chars"])
                if len(text) < 5:
                    raise ValueError("The text must be at least 5 characters")
                if op == "block_text" and len(text) < MANUAL_TEXT_MIN_CHARS:
                    raise ValueError(f"Use at least {MANUAL_TEXT_MIN_CHARS} characters of the spam message. SpamGuard "
                                     "blocks spam messages, not single words or names")
                sender = str(body.get("sender") or "")
                if op == "mark_spam" and sender and (sender in self.allow_senders or self.is_known(sender)):
                    raise ValueError(f"{sender} is someone SpamGuard knows, so it won't block what they say. "
                                     "If they keep repeating it, the repeat guard already slows that down")
                key = text_key(text)
                self.suppressed.pop(key, None)
                self.blocks.pop(key, None)
                channel = body.get("channel") if body.get("channel") in self.cfg["channels"] else "Public"
                self._add_block(key, "text", text, "Marked as spam by you" if op == "mark_spam" else "Added by you",
                                "manual", channel=channel,
                                ttl=int(body.get("ttl_seconds") or self.cfg["block_ttl_seconds"]))
                msg = f"Blocking messages containing \"{text}\""
            elif op == "preview_now":
                if self.evidence is None:
                    raise ValueError("Turn on the evidence log first: the check replays what it has recorded")
                if not self.cfg.get("level_preview", True):
                    raise ValueError("Working this out is turned off in Settings, under Evidence log")
                if self._preview_busy:
                    raise ValueError("It is already being worked out")
                if time.time() - max(self._preview_tried, (self.level_preview or {}).get("ran") or 0) < 600:
                    raise ValueError("It was worked out a few minutes ago. Try again in 10 minutes")
                self.refresh_level_preview(force=True)
                msg = "Working out what each level would have held. It takes a few minutes"
            elif op == "label":
                lab = body.get("label")
                if lab not in ("spam", "not_spam", "none"):
                    raise ValueError("Label a message as spam, fine, or clear the label")
                sender, text = str(body.get("sender") or ""), str(body.get("text") or "")
                key = str(body.get("packet") or "") or f"{sender}|{text}"
                if not key.strip("|"):
                    raise ValueError("Which message?")
                self.ev({"type": "label", "label": lab, "sender": sender, "text": text,
                         "path": body.get("path"), "packet": body.get("packet"), "by": "label"})
                self.labels.pop(key, None)
                if lab != "none":
                    self.labels[key] = lab
                    while len(self.labels) > 1000:
                        self.labels.popitem(last=False)
                msg = {"spam": "Labelled as spam", "not_spam": "Labelled as fine", "none": "Label cleared"}[lab] + (
                    ". Labels are kept in the evidence log, for checking SpamGuard's accuracy later."
                    if self.evidence is not None else ". Turn on the evidence log to keep labels.")
            elif op == "not_spam":
                self.genuine_marks.append(now)
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
                if self.covers_everyone(b):
                    if body.get("permanent"):
                        raise ValueError("Blocks that also stop people SpamGuard knows (on message text, or on anything "
                                         "passing through a repeater) can't be kept for ever; they last at most 7 days")
                    b["expires"] = min(max(b["expires"], now) + int(body.get("seconds", 3600)), now + TEXT_BLOCK_MAX_SECONDS)
                elif body.get("permanent"):
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
            elif op == "forget_known":
                name = str(body.get("name", ""))
                was = self.known.pop(name, None) is not None
                trusted = name in self.allow_senders
                self.allow_senders.discard(name)
                if not was and not trusted:
                    raise ValueError("SpamGuard doesn't know that name")
                self.note(f"Forgot '{name}' as a known person (by hand)")
                msg = (f"Forgot '{name}'. They count as new again until they've sent "
                       f"{int(self.cfg.get('known_min_msgs', 1))} genuine messages.")
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
            elif op == "add_channel" and not str(body.get("key", "")).strip() and \
                    len([p for p in re.split(r"[\s,;]+", str(body.get("name", ""))) if p]) > 1:
                # several hashtag channels at once (pasted list)
                names = [p for p in re.split(r"[\s,;]+", str(body.get("name", ""))) if p]
                bad = [p for p in names if not p.startswith("#")]
                if bad:
                    raise ValueError("To add several at once, give hashtag channels only (e.g. #chat #test). "
                                     "Private channels need adding one at a time with their key.")
                for p in names:
                    self.extra_channels[p] = hashtag_secret(p)
                self.rebuild_cfg()
                msg = f"SpamGuard can now read {len(names)} more channels"
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
            elif op == "add_openhop_channel":
                names = body.get("names") or [body.get("name")]
                added = [n for n in names if isinstance(n, str) and n in self.openhop_channels]
                if not added:
                    raise ValueError("openHop doesn't list that channel any more")
                for n in added:
                    self.extra_channels[n] = self.openhop_channels[n]
                self.rebuild_cfg()
                msg = f"SpamGuard can now read {added[0]}" if len(added) == 1 else f"SpamGuard can now read {len(added)} more channels"
            elif op == "remove_channel":
                self.extra_channels.pop(str(body.get("name", "")), None)
                self.rebuild_cfg()
            elif op == "fg_start_now":
                if self.fg.get("ready"):
                    raise ValueError("FloodGuard has already finished learning")
                self.fg["start_now"] = True
                self.fg_learn(time.time() if not self.fg.get("learn_start") else max(time.time(), float(self.fg["learn_start"])))
                if not self.fg.get("ready"):   # fg_learn waits for enough data; you asked to start now
                    self.fg.update(ready=time.time(), learnt_at=time.time())
                    self.note("FloodGuard started acting before it finished learning, with the recommended values.")
                self.sync_pending = True
                msg = "FloodGuard now acts on floods"
            elif op == "fg_relearn":
                # Every FloodGuard setting back to FloodGuard's own, and three days of learning from scratch.
                # It keeps protecting meanwhile (with the recommended values) if it was already acting.
                for k in [m["key"] for m in SETTINGS_META if m["group"] == "FloodGuard" and m["key"] != "floodguard"]:
                    self.settings.pop(k, None)
                f = self.fg
                f.update(learnt={}, learnt_at=None, learn_start=time.time(), limit=None)
                if f.get("ready"):
                    f["relearn"] = True
                self.fg_hops.clear()
                self.fg_adv.clear()
                self._hop_pending.clear()
                self.rebuild_cfg()
                self.sync_pending = True
                self.note(f"FloodGuard settings reset to its own values. It is learning this repeater's traffic again for "
                          f"{FG_LEARN_DAYS} days" + (", and keeps protecting with the recommended values meanwhile." if f.get("relearn") else "."))
                msg = f"FloodGuard is learning again for {FG_LEARN_DAYS} days"
            elif op == "fg_auto":
                k = str(body.get("key") or "")
                if k not in FG_AUTO_KEYS:
                    raise ValueError("that setting isn't learnt automatically")
                self.settings.pop(k, None)
                self.rebuild_cfg()
                self.sync_pending = True
                self.note(f"{META_BY_KEY[k]['label']}: back to automatic")
                msg = "Back to automatic"
            elif op == "clear_auto":
                # Hold each cleared block off, or the next decide() rebuilds it from the same evidence
                # and it looks like the clear did nothing.
                for k in [k for k, b in self.blocks.items() if b.get("source") != "manual"]:
                    b = self.blocks.pop(k)
                    if b.get("source") == "dedupe":
                        self.release_duplicate(b)   # forgiven: new copies start a new block
                    else:
                        self.suppressed[k] = now + 86400
                self.note("Cleared all automatic blocks")
                msg = ("Automatic blocks cleared. SpamGuard won't re-create those for 24 hours "
                       "(Exceptions > Not re-blocked > Clear undoes that). New spam can still make new ones.")
            elif op == "clear_suppressed":
                self.suppressed.clear()
            elif op == "clear_history":
                if str(body.get("confirm", "")).strip().upper() != "RESET":
                    raise ValueError("Type RESET to confirm clearing the spam history")
                n = sum(v.get("c", 0) + v.get("x", 0) for v in self.hist.values())
                self.hist.clear()
                self.catches.clear()
                self.held.clear()
                self.held_names.clear()
                self.note(f"Spam history cleared ({n} spam message{'' if n == 1 else 's'} over the last 8 days); "
                          "blocks, settings and the evidence log are unchanged")
                self._important = True
                msg = "Spam history cleared. The charts and Spam sources start again from now."
            elif op == "profile_save":
                name = str(body.get("name", "")).strip()[:40]
                if not name:
                    raise ValueError("Give the profile a name")
                if name not in self.profiles and len(self.profiles) >= MAX_PROFILES:
                    raise ValueError(f"At most {MAX_PROFILES} profiles; delete one first")
                self.profiles[name] = dict(self.current_profile(), saved=now)
                self.profile_in_use = name
                msg = f"Saved the current settings as '{name}'"
            elif op == "profile_import":
                p = self.check_profile(body.get("profile"))
                name = str(body.get("name") or (body.get("profile") or {}).get("name") or "Imported profile").strip()[:40]
                base, i = name, 2
                while name in self.profiles:
                    name, i = f"{base} ({i})", i + 1
                if len(self.profiles) >= MAX_PROFILES:
                    raise ValueError(f"At most {MAX_PROFILES} profiles; delete one first")
                self.profiles[name] = dict(p, saved=now)
                msg = f"Imported '{name}'. Nothing has changed yet: press Apply when you want to use it."
            elif op == "profile_apply":
                name = str(body.get("name", ""))
                if name not in self.profiles:
                    raise ValueError("That profile no longer exists")
                self.apply_profile(self.profiles[name])
                self.profile_in_use = name
                self.note(f"Applied settings profile '{name}'")
                msg = f"Settings profile '{name}' applied"
            elif op == "profile_delete":
                self.profiles.pop(str(body.get("name", "")), None)
                if self.profile_in_use not in self.profiles:
                    self.profile_in_use = None
            elif op in ("clear_held", "clear_recent"):
                self.view_marks[op.split("_")[1]] = now
                msg = "Cleared. Anything new still shows up here, and the evidence log keeps everything."
            elif op == "hide_source":
                hop = str(body.get("hop", "")).upper().strip()
                if not hop:
                    raise ValueError("Which repeater code?")
                self.hidden_sources[hop] = now
                msg = f"Removed {hop} from Spam sources. It comes back if spam arrives through it again."
            elif op == "reset_all":
                if str(body.get("confirm", "")).strip().upper() != "RESET":
                    raise ValueError("Type RESET to confirm starting again from scratch")
                self.reset_all()
                msg = ("SpamGuard is starting again from scratch: every block, setting and exception has been "
                       "cleared, and it's watching for spam afresh. The page shows what happens from now on; "
                       "the evidence log keeps everything.")
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


ACTIONS = {"unblock", "block_hop", "block_route", "accept_route", "dismiss_route", "block_text", "mark_spam", "not_spam", "extend", "rule_action", "hop_mode",
           "forget_path", "allow_hop", "unallow_hop", "allow_sender", "unallow_sender", "forget_known", "allow_text",
           "unallow_text", "add_channel", "add_openhop_channel", "profile_save", "profile_import", "profile_apply", "profile_delete", "remove_channel", "clear_auto", "clear_suppressed", "fg_start_now", "fg_auto", "fg_relearn",
           "allow_origin", "unallow_origin", "lockdown", "reset_all", "clear_history", "clear_held", "clear_recent",
           "hide_source", "label", "preview_now"}


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
            if path == "/handover":
                from urllib.parse import parse_qs, urlparse
                st = guard.handover_state((parse_qs(urlparse(self.path).query).get("key") or [""])[0])
                return self._send(200, st) if st is not None else self._send(403, {"error": "no handover under way"})
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
            # Changes only come as JSON. A browser won't send JSON to another site without asking first, so a
            # web page elsewhere can't quietly change SpamGuard's settings through someone's browser.
            if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
                return self._send(415, {"error": "Changes must be sent as JSON"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                path = self.path.split("?")[0].strip("/")
                if path == "settings":
                    return self._send(200, guard.apply_settings(body))
                if path in ("check_update", "install_update"):
                    return self._send(200, guard.update_action(path, body))
                if path == "move_to_plugin":
                    return self._send(200, guard.start_move_to_plugin())
                if path == "openhop_fix":
                    return self._send(200, guard.request_openhop_fix("asked for on the page"))
                if path == "messages_for":
                    return self._send(200, guard.messages_for(body))
                if path == "quarantine":
                    return self._send(200, guard.quarantine(body))
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
    # Optional settings from the environment, mainly for Docker. The config file wins when both are set,
    # except for the token above.
    env = {"OPENHOP_URL": "openhop_url", "SPAMGUARD_MODE": "mode", "SPAMGUARD_SENSITIVITY": "sensitivity",
           "SPAMGUARD_LEVEL": "level",
           "SPAMGUARD_PASSWORD": "listen_api_key"}
    for var, key in env.items():
        if os.environ.get(var) and key not in cfg:
            cfg[key] = os.environ[var]
    if os.environ.get("SPAMGUARD_CHANNELS") and "hashtag_channels" not in cfg:
        cfg["hashtag_channels"] = [c.strip() for c in os.environ["SPAMGUARD_CHANNELS"].split(",") if c.strip()]
    data = os.environ.get("SPAMGUARD_DATA")
    if data:
        cfg.setdefault("state_file", os.path.join(data, "state.json"))
        cfg.setdefault("evidence_dir", os.path.join(data, "evidence"))
    return cfg


def remove_rules(cfg: dict) -> int:
    """Take SpamGuard's rules (names starting "spamguard:") and its known-people list out of openHop,
    leaving everything else in place. Returns 0 when done."""
    url = str(cfg.get("openhop_url") or DEFAULT_CONFIG["openhop_url"]).rstrip("/") + "/api/policy"

    def call(method, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if cfg.get("api_key"):
            req.add_header("X-API-Key", str(cfg["api_key"]))
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read().decode() or "{}")
        if isinstance(res, dict) and res.get("success") is False:
            raise RuntimeError(res.get("error") or res.get("message") or "API error")
        return res

    try:
        res = call("GET")
        pe = dict((res.get("data", res) or {}).get("policy_engine") or {})
        rules = [r for r in (pe.get("rules") or []) if isinstance(r, dict)]
        keep = [r for r in rules if not str(r.get("name", "")).startswith("spamguard:")]
        objects = pe.get("objects") if isinstance(pe.get("objects"), dict) else {}
        had_list = objects.pop("spamguard", None) is not None
        groups = objects.get("channel_hash_groups")
        if isinstance(groups, dict) and groups.pop("spamguard", None) is not None:
            had_list = True
            if not groups:
                objects.pop("channel_hash_groups", None)
        had_list = (objects.pop(OWNER_KEY, None) is not None) or had_list
        if len(keep) != len(rules) or had_list:
            pe["rules"], pe["objects"] = keep, objects
            call("POST", {"policy_engine": pe})
        print(f"Removed {len(rules) - len(keep)} SpamGuard rule(s); {len(keep)} of your own rule(s) left in place.")
        return 0
    except Exception as e:
        print(f"Could not update openHop's rules ({e}).", file=sys.stderr)
        return 1


def main():
    ap = argparse.ArgumentParser(description="openHop SpamGuard")
    ap.add_argument("--config", default="/etc/openhop_spamguard/config.yaml")
    ap.add_argument("--once", action="store_true", help="check once, print a summary, exit")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--remove-rules", action="store_true",
                    help="take SpamGuard's rules and known-people list out of openHop, then exit (used when removing it)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if AES is None:
        raise SystemExit("pycryptodome missing - run with openHop's venv python: "
                         "/opt/openhop_repeater/venv/bin/python spamguard.py, or pip install pycryptodome")
    if args.remove_rules:
        raise SystemExit(remove_rules(load_config(args.config)))
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
    servers: list = []

    def serve() -> bool:
        try:
            srv = QuietServer((guard.cfg["listen_host"], int(guard.cfg["listen_port"])), make_handler(guard))
        except OSError:
            return False
        servers.append(srv)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return True

    if not serve():
        if not IN_PLUGIN:
            raise SystemExit(f"Port {guard.cfg['listen_port']} is already in use - is another SpamGuard running?")
        # As a plugin, the port may still belong to the SpamGuard this one is taking over from: keep
        # protecting the repeater and open the page as soon as the port is free.
        log.warning("Port %s is in use (another SpamGuard?); the web page will open when it is free",
                    guard.cfg["listen_port"])

        def retry():
            while not stop.is_set() and not serve():
                stop.wait(5)
            if servers:
                log.info("Web page now open on port %s", guard.cfg["listen_port"])
        threading.Thread(target=retry, daemon=True, name="port").start()
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
        if IN_PLUGIN:
            guard.release_on_stop()
        for srv in servers:
            srv.shutdown()


if __name__ == "__main__":
    main()
