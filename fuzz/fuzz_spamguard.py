"""Atheris fuzz harness: throws arbitrary bytes and text at the parts of SpamGuard that read data sent by strangers
over the radio. Anything other than a clean result or a clean refusal is a bug.

Run it by hand:  python fuzz/fuzz_spamguard.py -max_total_time=60
"""
import os
import sys

import atheris

with atheris.instrument_imports():
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import spamguard as sg

CHANNELS = {"Public": sg.PUBLIC_CHANNEL_KEY}


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)
    which = fdp.ConsumeIntInRange(0, 3)
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
    else:
        texts = [fdp.ConsumeUnicodeNoSurrogates(120) for _ in range(fdp.ConsumeIntInRange(0, 5))]
        sg.common_words(texts, fdp.ConsumeIntInRange(1, 60))
        sg.common_substring(texts, fdp.ConsumeIntInRange(1, 60))


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()
