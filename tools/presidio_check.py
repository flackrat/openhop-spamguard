#!/usr/bin/env python3
"""A second opinion on personal details, using Microsoft Presidio: it looks at the words in lines a change adds
(comments and quoted text in code, every line of documentation) and points out what reads like a person's
name, a place, an email address or a phone number.

Presidio guesses from context, so it is advisory: it warns and never fails. To keep it useful it only reports
names and places that are new to the repository: a word used three or more times in the files already
(Docker, Overview, Activity...) is never reported. Like tools/privacy_check.py, it says only where and what
kind of thing it saw, never the text itself.

Usage:
  presidio_check.py --diff BASE        lines added since BASE
  presidio_check.py --staged           lines staged for the next commit
Needs: pip install -r requirements/presidio.txt
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from privacy_check import ALWAYS_ALLOWED, ROOT, SKIP_PATHS, added_lines, load_allowed, tracked_files  # noqa: E402

ENTITIES = ["PERSON", "LOCATION", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "UK_NHS"]
NAMES = {"PERSON": "a person's name", "LOCATION": "a place", "EMAIL_ADDRESS": "an email address",
         "PHONE_NUMBER": "a phone number", "CREDIT_CARD": "a card number", "IBAN_CODE": "a bank account number",
         "UK_NHS": "an NHS number"}
QUOTED = re.compile(r'"([^"\\\n]{4,})"|\'([^\'\\\n]{4,})\'')
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]+")
DOC = (".md", ".txt", ".yml", ".yaml", ".html", ".toml")


def readable_parts(path: str, line: str) -> list[str]:
    """The human-language parts of a line: comments and quoted text in code, the whole line in documents."""
    if path.endswith(".py"):
        parts = [m.group(1) or m.group(2) for m in QUOTED.finditer(line)]
        i = line.find("#")
        if i >= 0:
            parts.append(line[i + 1:])
        return parts
    if path.endswith(DOC):
        if sum(line.count(c) for c in "{};=`") >= 3:   # script or style inside a page, not prose
            return []
        return [re.sub(r"<[^>]+>", " ", line)]
    return []


def known_words() -> set[str]:
    """Words already used three or more times in the repository: its everyday vocabulary."""
    c: collections.Counter = collections.Counter()
    for f in tracked_files():
        try:
            with open(os.path.join(ROOT, f), encoding="utf-8", errors="ignore") as fh:
                c.update(w.lower() for w in WORD.findall(fh.read()))
        except OSError:
            pass
    return {w for w, n in c.items() if n >= 3}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--diff", metavar="BASE")
    g.add_argument("--staged", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.6)
    a = ap.parse_args()
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
    except ImportError:
        print("presidio check: Presidio isn't installed (pip install -r requirements/presidio.txt)")
        return 0
    nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy",
                                               "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]}).create_engine()
    engine = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
    vocab, allowed = known_words(), load_allowed()
    gh = bool(os.environ.get("GITHUB_ACTIONS"))
    rng = ["--cached"] if a.staged else [f"{a.diff}...HEAD"]
    seen = 0
    for path, n, line in added_lines(rng):
        if SKIP_PATHS.search(path):
            continue
        kinds = set()
        for part in readable_parts(path, line):
            for r in engine.analyze(text=part, language="en", entities=ENTITIES, score_threshold=a.threshold):
                s = part[r.start:r.end]
                if any(x and (x in s or s in x) for x in allowed) or any(rx.search(s) for rx in ALWAYS_ALLOWED):
                    continue
                if r.entity_type in ("PERSON", "LOCATION"):
                    words = [w.lower() for w in WORD.findall(s)]
                    # only proper names that are new here; everyday words of this repository are skipped
                    if not words or all(w in vocab for w in words) or not any(w[:1].isupper() for w in WORD.findall(s)):
                        continue
                kinds.add(NAMES.get(r.entity_type, r.entity_type))
        for k in sorted(kinds):
            seen += 1
            msg = f"{path}:{n}: this may be {k}. If it's real, take it out; if it's made up, it's fine."
            print(f"::warning file={path},line={n}::{msg}" if gh else msg)
    print(f"presidio check: {seen} thing(s) to look at" if seen else "presidio check: nothing to look at")
    return 0


if __name__ == "__main__":
    sys.exit(main())
