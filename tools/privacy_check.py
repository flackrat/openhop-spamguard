#!/usr/bin/env python3
"""Stops personal details reaching the repository: places, coordinates, addresses, email addresses and the
like, plus anything on a private blocklist that never appears in the repository itself.

Usage:
  privacy_check.py --tree                 every tracked file
  privacy_check.py --diff BASE            lines added since BASE, and the commit messages since BASE
  privacy_check.py --staged               lines staged for the next commit (for a local pre-commit hook)
  privacy_check.py --text-env NAME ...    the text in these environment variables (a pull request title/body)

The private blocklist comes from the PRIVACY_BLOCKLIST and PRIVACY_NAMES, PRIVACY_NAMES2 ... environment variables
(GitHub Actions secrets; a value starting "gz:" is gzip then base64) and/or --blocklist FILE (more than one may be
given). One entry per line; blank lines and lines starting with # are ignored. An entry starting with "re:" is a
regular expression, "w:" is plain text matched as a whole word, anything else is plain text, all ignoring case.

What was found is never printed, only where and which check, because the output of a public workflow is
public too. Exit status 1 means something was found.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import os
import re
import subprocess
import sys

ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
ALLOW_FILE = os.path.join(ROOT, ".privacy-allow")

# Patterns that are safe to publish: they describe kinds of personal detail, not any particular one.
GENERIC = {
    "email address": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"),
    "map coordinates": re.compile(r"(?<![\w.])-?\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}(?![\w.])"),
    "UK postcode": re.compile(r"\b(?:[A-PR-UWYZ][A-HK-Y]?\d[A-Z\d]?) ?\d[ABD-HJLNP-UW-Z]{2}\b"),
    "grid locator": re.compile(r"\b[A-R]{2}\d{2}[A-X]{2}\b"),
    "home network address": re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "phone number": re.compile(r"(?<!\w)(?:\+44\s?7\d{3}|07\d{3})\s?\d{3}\s?\d{3}(?!\w)"),
    # A British or Irish amateur radio callsign (made-up ones in tests start with Q, which is never issued).
    "radio callsign": re.compile(r"\b(?:2[DEIJMUW]|G[DIJMUW]?|M[DIJMUW]?|EI)\d[A-Z]{2,3}\b"),
}
# Any coordinate pair in Britain or Ireland, at any precision and however written. Test data uses made-up places
# in the USA, so these are never allowed, not even through .privacy-allow.
_NUM = r"-?\d{1,3}\.\d+"
_PAIR = re.compile(rf"(?<![\w.])({_NUM})(?:\s*,\s*|\s+)({_NUM})(?![\w.])")
_KEYED = re.compile(rf"""["']?lat(?:itude)?["']?\s*[:=]\s*({_NUM})[^\n]{{0,80}}?["']?lon(?:gitude)?["']?\s*[:=]\s*({_NUM})""")


def uk_place(text: str) -> bool:
    for m in list(_PAIR.finditer(text)) + list(_KEYED.finditer(text)):
        lat, lon = float(m.group(1)), float(m.group(2))
        if 49.5 <= lat <= 61.0 and -11.0 <= lon <= 2.5:
            return True
    return False
# Always fine: no-reply addresses (including the one GitHub signs Dependabot updates with) and the documentation's own example values.
ALWAYS_ALLOWED = [
    re.compile(r"noreply@anthropic\.com|\bsupport@github\.com\b|@users\.noreply\.github\.com|@example\.(?:com|org|net)\b|@[\w.-]+\.example\b"),
]
SKIP_PATHS = re.compile(r"(^|/)(LICENSE|\.privacy-allow|package-lock\.json)$|\.(png|jpe?g|gif|ico|woff2?|ttf|whl|gz|zip|pdf)$")


def load_allowed() -> list[str]:
    """Exact strings that look personal but are made up (example addresses, invented test coordinates)."""
    try:
        with open(ALLOW_FILE, encoding="utf-8") as f:
            return [ln.rstrip("\n") for ln in f if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def _env_lists() -> list[str]:
    """PRIVACY_BLOCKLIST plus PRIVACY_NAMES, PRIVACY_NAMES2 and so on. A value starting "gz:" is gzip, then base64,
    so a long list of names still fits in a GitHub secret."""
    lines = []
    for key in sorted(os.environ):
        if key == "PRIVACY_BLOCKLIST" or re.fullmatch(r"PRIVACY_NAMES\d*", key):
            val = os.environ.get(key) or ""
            if val.startswith("gz:"):
                try:
                    val = gzip.decompress(base64.b64decode(val[3:])).decode("utf-8")
                except (ValueError, OSError):
                    print(f"privacy check: {key} can't be read", file=sys.stderr)
                    val = ""
            lines += val.splitlines()
    return lines


class Blocklist(list):
    """The compiled entries, plus the plain-text ones kept as lowered text and indexed by their first three
    characters, so a list of thousands of names is checked in one pass over each line."""

    def __init__(self):
        super().__init__()
        self.lit: dict[str, list[tuple[int, str, bool]]] = {}
        self.short: list[tuple[int, str, bool]] = []
        self.rx: list[tuple[int, re.Pattern]] = []

    def add(self, entry: str) -> None:
        if entry.startswith("re:"):
            rx = re.compile(entry[3:], re.I)
            self.rx.append((len(self) + 1, rx))
        else:
            whole = entry.startswith("w:")
            text = entry[2:] if whole else entry
            rx = re.compile((r"(?<![A-Za-z0-9])" + re.escape(text) + r"(?![A-Za-z0-9])") if whole else re.escape(text), re.I)
            low = text.lower()
            item = (len(self) + 1, low, whole)
            if len(low) >= 3:
                self.lit.setdefault(low[:3], []).append(item)
            else:
                self.short.append(item)
        self.append(rx)

    def hits(self, text: str) -> list[int]:
        found = set()
        for i, rx in self.rx:
            if rx.search(text):
                found.add(i)
        low = text.lower()
        cands = list(self.short)
        for k in range(len(low) - 2):
            got = self.lit.get(low[k:k + 3])
            if got:
                cands.extend((i, t, w, k) for i, t, w in got)
        for c in cands:
            i = c[0]
            if i in found:
                continue
            starts = [c[3]] if len(c) == 4 else [m.start() for m in re.finditer(re.escape(c[1]), low)]
            for st in starts:
                if not low.startswith(c[1], st):
                    continue
                end = st + len(c[1])
                if c[2] and ((st and low[st - 1].isalnum() and low[st - 1].isascii())
                             or (end < len(low) and low[end].isalnum() and low[end].isascii())):
                    continue
                found.add(i)
                break
        return sorted(found)


def _env_lists() -> list[str]:
    """PRIVACY_BLOCKLIST plus PRIVACY_NAMES, PRIVACY_NAMES2 and so on. A value starting "gz:" is gzip, then base64,
    so a long list of names still fits in a GitHub secret."""
    lines = []
    for key in sorted(os.environ):
        if key == "PRIVACY_BLOCKLIST" or re.fullmatch(r"PRIVACY_NAMES\d*", key):
            val = os.environ.get(key) or ""
            if val.startswith("gz:"):
                try:
                    val = gzip.decompress(base64.b64decode(val[3:])).decode("utf-8")
                except (ValueError, OSError):
                    print(f"privacy check: {key} can't be read", file=sys.stderr)
                    val = ""
            lines += val.splitlines()
    return lines


def load_blocklist(paths) -> Blocklist:
    lines = _env_lists()
    for path in ([paths] if isinstance(paths, str) else paths or []):
        try:
            with open(os.path.expanduser(path), encoding="utf-8") as f:
                lines += f.read().splitlines()
        except OSError:
            print(f"privacy check: can't read the blocklist file {path}", file=sys.stderr)
    out = Blocklist()
    for entry in lines:
        entry = entry.strip()
        if not entry or entry.startswith("#"):
            continue
        try:
            out.add(entry)
        except re.error:
            print(f"privacy check: blocklist entry #{len(out) + 1} isn't a valid pattern", file=sys.stderr)
    return out


def check_line(text: str, allowed: list[str], block) -> list[str]:
    hits = []
    if isinstance(block, Blocklist):
        nums = block.hits(text)
    else:
        nums = [i for i, rx in enumerate(block, 1) if rx.search(text)]
    hits += [f"private blocklist entry #{i}" for i in nums]
    if uk_place(text):
        hits.append("a place in Britain or Ireland")
    for name, rx in GENERIC.items():
        for m in rx.finditer(text):
            s = m.group(0)
            if any(a.search(s) for a in ALWAYS_ALLOWED) or any(s in a or a in s for a in allowed if a):
                continue
            hits.append(name)
            break
    return hits


def tracked_files() -> list[str]:
    return [f for f in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
            if not SKIP_PATHS.search(f)]


def added_lines(args: list[str]):
    """(path, line number, text) for each line added in a git diff."""
    out = subprocess.run(["git", "diff", "--no-color", "-U0", *args], cwd=ROOT, capture_output=True, text=True).stdout
    path, n = None, 0
    for row in out.splitlines():
        if row.startswith("+++ "):
            path = row[6:] if row.startswith("+++ b/") else None
        elif row.startswith("@@"):
            m = re.search(r"\+(\d+)", row)
            n = int(m.group(1)) if m else 0
        elif row.startswith("+") and path and not SKIP_PATHS.search(path):
            yield path, n, row[1:]
            n += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tree", action="store_true")
    g.add_argument("--diff", metavar="BASE")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--text-env", nargs="+", metavar="NAME")
    ap.add_argument("--blocklist", metavar="FILE", action="append", help="a local blocklist file, kept outside the repository")
    a = ap.parse_args()
    allowed, block = load_allowed(), load_blocklist(a.blocklist)
    if not block:
        print("::warning::privacy check: no private blocklist set, so only the general checks ran" if os.environ.get("GITHUB_ACTIONS")
              else "privacy check: no private blocklist set, so only the general checks ran")
    found = 0

    def report(where: str, hits: list[str]):
        nonlocal found
        for h in hits:
            found += 1
            print(f"::error::{where}: {h}" if os.environ.get("GITHUB_ACTIONS") else f"{where}: {h}")

    if a.tree:
        for f in tracked_files():
            try:
                with open(os.path.join(ROOT, f), encoding="utf-8", errors="ignore") as fh:
                    for n, line in enumerate(fh, 1):
                        report(f"{f}:{n}", check_line(line, allowed, block))
            except (IsADirectoryError, FileNotFoundError):
                pass
    elif a.text_env:
        for name in a.text_env:
            for n, line in enumerate((os.environ.get(name) or "").splitlines(), 1):
                report(f"{name} line {n}", check_line(line, allowed, block))
    else:
        rng = ["--cached"] if a.staged else [f"{a.diff}...HEAD"]
        for path, n, line in added_lines(rng):
            report(f"{path}:{n}", check_line(line, allowed, block))
        if a.diff:
            log = subprocess.run(["git", "log", "--format=%H%n%B%x00", f"{a.diff}..HEAD"], cwd=ROOT,
                                 capture_output=True, text=True).stdout
            for entry in log.split("\0"):
                lines = entry.strip().splitlines()
                for n, line in enumerate(lines[1:], 1):
                    report(f"commit {lines[0][:9]} message line {n}", check_line(line, allowed, block))
    print(f"privacy check: {'nothing found' if not found else f'{found} finding(s)'}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
