"""Writes a CycloneDX software bill of materials for a release.

Lists the release itself and every pinned requirement (name, version, hashes) from requirements.txt.
Standard library only. Usage: python3 tools/make_sbom.py OUTFILE
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def version():
    m = re.search(r'^VERSION = "([0-9.]+)"$', open(os.path.join(ROOT, "spamguard.py")).read(), re.M)
    return m.group(1)


def pinned():
    text = open(os.path.join(ROOT, "requirements.txt")).read().replace("\\\n", " ")
    out = []
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;]+)(.*)$", line.strip())
        if m:
            out.append((m.group(1), m.group(2), re.findall(r"--hash=sha256:([0-9a-f]{64})", m.group(3))))
    return out


def build():
    v = version()
    comps = []
    for name, ver, hashes in pinned():
        c = {"type": "library", "name": name, "version": ver, "purl": "pkg:pypi/%s@%s" % (name.lower(), ver)}
        if hashes:
            c["hashes"] = [{"alg": "SHA-256", "content": h} for h in hashes]
        comps.append(c)
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {"type": "application", "name": "openhop-spamguard", "version": v,
                                   "purl": "pkg:github/flackrat/openhop-spamguard@v" + v}},
        "components": comps,
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "sbom.cdx.json"
    with open(out, "w") as f:
        json.dump(build(), f, indent=1)
    print("wrote %s (%d components)" % (out, len(build()["components"])))
