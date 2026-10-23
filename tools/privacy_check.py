#!/usr/bin/env python3
"""Stops personal details reaching the repository: places, coordinates, addresses, email addresses and the
like, plus anything on a private blocklist that never appears in the repository itself.

Usage:
  privacy_check.py --tree                 every tracked file
  privacy_check.py --diff BASE            lines added since BASE, and the commit messages since BASE
  privacy_check.py --staged               lines staged for the next commit (for a local pre-commit hook)
  privacy_check.py --text-env NAME ...    the text in these environment variables (a pull request title/body)

The private blocklist comes from the PRIVACY_BLOCKLIST environment variable (a GitHub Actions secret) and/or
--blocklist FILE. One entry per line; blank lines and lines starting with # are ignored. An entry starting
with "re:" is a regular expression, anything else is matched as plain text, ignoring case.

What was found is never printed, only where and which check, because the output of a public workflow is
public too. Exit status 1 means something was found.
"""
from __future__ import annotations

import argparse
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
}
# Always fine: no-reply addresses and the documentation's own example values.
ALWAYS_ALLOWED = [
    re.compile(r"noreply@anthropic\.com|@users\.noreply\.github\.com|@example\.(?:com|org|net)\b|@[\w.-]+\.example\b"),
]
SKIP_PATHS = re.compile(r"(^|/)(LICENSE|\.privacy-allow|package-lock\.json)$|\.(png|jpe?g|gif|ico|woff2?|ttf|whl|gz|zip|pdf)$")


def load_allowed() -> list[str]:
    """Exact strings that look personal but are made up (example addresses, invented test coordinates)."""
    try:
        with open(ALLOW_FILE, encoding="utf-8") as f:
            return [l.rstrip("\n") for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        return []


def load_blocklist(path: str | None) -> list[re.Pattern]:
    lines = (os.environ.get("PRIVACY_BLOCKLIST") or "").splitlines()
    if path:
        try:
            with open(os.path.expanduser(path), encoding="utf-8") as f:
                lines += f.read().splitlines()
        except OSError:
            print(f"privacy check: can't read the blocklist file {path}", file=sys.stderr)
    out = []
    for l in lines:
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        try:
            out.append(re.compile(l[3:], re.I) if l.startswith("re:") else re.compile(re.escape(l), re.I))
        except re.error:
            print(f"privacy check: blocklist entry #{len(out) + 1} isn't a valid pattern", file=sys.stderr)
    return out


def check_line(text: str, allowed: list[str], block: list[re.Pattern]) -> list[str]:
    hits = []
    for i, rx in enumerate(block, 1):
        if rx.search(text):
            hits.append(f"private blocklist entry #{i}")
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
    for l in out.splitlines():
        if l.startswith("+++ "):
            path = l[6:] if l.startswith("+++ b/") else None
        elif l.startswith("@@"):
            m = re.search(r"\+(\d+)", l)
            n = int(m.group(1)) if m else 0
        elif l.startswith("+") and path and not SKIP_PATHS.search(path):
            yield path, n, l[1:]
            n += 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--tree", action="store_true")
    g.add_argument("--diff", metavar="BASE")
    g.add_argument("--staged", action="store_true")
    g.add_argument("--text-env", nargs="+", metavar="NAME")
    ap.add_argument("--blocklist", metavar="FILE", help="a local blocklist file, kept outside the repository")
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
