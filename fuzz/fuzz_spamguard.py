"""Atheris fuzz harness: throws arbitrary bytes and text at the parts of SpamGuard that read data sent by strangers
over the radio, and at what the web page accepts (addresses, host names, settings). Anything other than a clean
result or a clean refusal is a bug.

Run it by hand:  python fuzz/fuzz_spamguard.py -max_total_time=60
"""
import os
import sys

import atheris

with atheris.instrument_imports():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import spamguard as sg

import json
import tempfile

CHANNELS = {"Public": sg.PUBLIC_CHANNEL_KEY}
_DIR = tempfile.mkdtemp(prefix="sg-fuzz-")
GUARD = sg.SpamGuard({"state_file": os.path.join(_DIR, "state.json"), "evidence_log": False,
                      "openhop_url": "http://127.0.0.1:9", "mode": "monitor"})
GUARD._save_state = lambda *a, **k: None
GUARD.request_sync = lambda *a, **k: None
GUARD.snapshot_settings = lambda *a, **k: None
KEYS = [m["key"] for m in sg.SETTINGS_META] + ["mode", "paused", "level", "sensitivity", "replace_own", "reset"]


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    which = fdp.ConsumeIntInRange(0, 5)
    if which == 0:
        # A packet as it arrives from the radio.
        sg.decrypt_group_text(fdp.ConsumeBytes(512), CHANNELS)
    elif which == 1:
        # A message as strangers write it: invisible characters, look-alike letters, emoji floods.
        text = fdp.ConsumeUnicodeNoSurrogates(400)
        norm = sg.normalise(text)
        sg.strip_emoji(text)
        sg.garbage_score(text)
        sg.is_garbage(text)
        sg.is_obfuscated(text)
        sg.shingles(norm)
        sg.middle_chunk(text, fdp.ConsumeIntInRange(1, 200))
        sg.text_key(text)
    elif which == 2:
        # A route as openHop reports it: a list, a string, or something unexpected.
        sg.parse_path(fdp.ConsumeUnicodeNoSurrogates(120))
    elif which == 4:
        # Who is asking and which name they say they are visiting: never an error, only yes or no.
        a = fdp.ConsumeUnicodeNoSurrogates(60)
        assert isinstance(sg.peer_is_local(a), bool)
        assert isinstance(sg.host_is_local(fdp.ConsumeUnicodeNoSurrogates(80), [a]), bool)
    elif which == 5:
        # A settings change from the page: anything is either applied or refused with a reason.
        body = {}
        for _ in range(fdp.ConsumeIntInRange(0, 4)):
            k = KEYS[fdp.ConsumeIntInRange(0, len(KEYS) - 1)] if fdp.ConsumeBool() else fdp.ConsumeUnicodeNoSurrogates(20)
            kind = fdp.ConsumeIntInRange(0, 4)
            body[k] = (fdp.ConsumeBool(), fdp.ConsumeInt(4), fdp.ConsumeUnicodeNoSurrogates(40),
                       [fdp.ConsumeUnicodeNoSurrogates(20)], None)[kind]
        try:
            GUARD.apply_settings(json.loads(json.dumps(body)))
        except (ValueError, TypeError):
            pass
        assert 0 <= int(GUARD.cfg.get("level", 50)) <= 100
        assert GUARD.cfg["mode"] in ("monitor", "protect")
        GUARD.settings.clear()
        GUARD.rebuild_cfg()
    else:
        texts = [fdp.ConsumeUnicodeNoSurrogates(120) for _ in range(fdp.ConsumeIntInRange(0, 5))]
        sg.common_words(texts, fdp.ConsumeIntInRange(1, 60))
        sg.common_substring(texts, fdp.ConsumeIntInRange(1, 60))


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
