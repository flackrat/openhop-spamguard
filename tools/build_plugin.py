"""Build SpamGuard's openHop plugin wheel: python3 tools/build_plugin.py [out_dir]

The wheel holds SpamGuard itself, a small start-up script, the page openHop's dashboard shows
under System > Plugins, and the openhop-plugin.json manifest. It prints the file name and its
sha256, which an openHop plugin catalogue entry needs."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ID = "openhop-spamguard"


def source_date() -> str:
    """The last commit's time (seconds since 1970), or a fixed date outside a git checkout."""
    try:
        out = subprocess.run(["git", "-C", HERE, "log", "-1", "--format=%ct"], capture_output=True, text=True,
                             check=True).stdout.strip()
        return out if out.isdigit() else "1704067200"
    except (OSError, subprocess.CalledProcessError):
        return "1704067200"


def version() -> str:
    """SpamGuard's version padded to the three numbers openHop's manifests require (5.19 -> 5.19.0)."""
    text = open(os.path.join(HERE, "spamguard.py"), encoding="utf-8").read()
    v = os.environ.get("SPAMGUARD_BUILD_VERSION") or re.search(r'^VERSION = "([0-9.]+)"$', text, re.M).group(1)
    parts = v.split(".")
    return ".".join((parts + ["0", "0"])[:3])


def build(out_dir: str) -> str:
    v = version()
    stage = tempfile.mkdtemp(prefix="sgplugin-")
    try:
        pkg = os.path.join(stage, "openhop_spamguard")
        os.makedirs(pkg)
        open(os.path.join(pkg, "__init__.py"), "w").write(f'__version__ = "{v}"\n')
        for f in ("spamguard.py", "ui.html", "replay.py"):
            shutil.copy2(os.path.join(HERE, f), pkg)
        shutil.copy2(os.path.join(HERE, "plugin", "plugin.py"), pkg)
        shutil.copytree(os.path.join(HERE, "plugin", "spamguard-ui"), os.path.join(pkg, "spamguard-ui"))
        manifest = {
            "schema": 1,
            "id": PLUGIN_ID,
            "name": "SpamGuard",
            "version": v,
            "description": "Stops MeshCore channel spam at this repeater, while regulars keep getting through, and with FloodGuard contains airtime floods of any packet type. "
                           "Paste an openHop API token into api_key, then press Open to reach SpamGuard's own page "
                           "(port 8091 unless you change listen_port).",
            # A small doorway page, so openHop's Plugins page has an Open button. openHop also lists any plugin
            # page as a choice for its main web page; if SpamGuard's is picked, the page and SpamGuard itself
            # put openHop's own dashboard straight back.
            "ui": {"type": "application", "entry": "spamguard-ui/index.html"},
            "runtime": {"type": "python", "entrypoint": "openhop-spamguard"},
            "config": {"defaults": {
                "api_key": "",
                "openhop_url": "http://127.0.0.1:8000",
                "mode": "monitor",
                "sensitivity": "balanced",
                "listen_port": 8091,
                "hashtag_channels": [],
                "listen_api_key": "",
            }},
        }
        open(os.path.join(stage, "openhop-plugin.json"), "w").write(json.dumps(manifest, indent=2) + "\n")
        open(os.path.join(stage, "pyproject.toml"), "w").write(
            '[build-system]\nrequires = ["setuptools>=69", "wheel"]\nbuild-backend = "setuptools.build_meta"\n')
        open(os.path.join(stage, "setup.py"), "w").write(f'''from setuptools import setup
setup(
    name="openhop-spamguard",
    version="{v}",
    description="SpamGuard with FloodGuard: spam and flood protection for openHop MeshCore repeaters (openHop plugin)",
    url="https://github.com/flackrat/openhop-spamguard",
    license="AGPL-3.0-or-later",
    packages=["openhop_spamguard"],
    package_data={{"openhop_spamguard": ["ui.html", "spamguard-ui/*"]}},
    data_files=[("share/openhop/plugins/{PLUGIN_ID}", ["openhop-plugin.json"])],
    # PyYAML is written the way its published files spell it. pip 23.0 (Raspberry Pi OS Bookworm) throws away the
    # ready-made piwheels build of "pyyaml" because the name's capitals differ, and then compiles it from source,
    # which takes a Pi 3 longer than openHop waits.
    install_requires=["pycryptodome>=3.15", "PyYAML>=5.4"],
    python_requires=">=3.9",
    entry_points={{"console_scripts": ["openhop-spamguard=openhop_spamguard.plugin:main"]}},
)
''')
        os.makedirs(out_dir, exist_ok=True)
        # Reproducible: every build of the same commit gives the same file, bit for bit. The timestamps inside
        # the wheel come from the last commit rather than the clock.
        env = dict(os.environ, SOURCE_DATE_EPOCH=os.environ.get("SOURCE_DATE_EPOCH") or source_date())
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-cache-dir", "-q",
                        "-w", out_dir, stage], check=True, env=env)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    wheel = os.path.join(out_dir, f"openhop_spamguard-{v}-py3-none-any.whl")
    digest = hashlib.sha256(open(wheel, "rb").read()).hexdigest()
    print(wheel)
    print(f"sha256 {digest}")
    return wheel


if __name__ == "__main__":
    build(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "dist")))
