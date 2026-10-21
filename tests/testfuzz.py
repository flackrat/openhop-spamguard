# Property-based ("fuzz") tests: SpamGuard reads text and packets sent by strangers over the radio, so the
# functions that handle that input must never crash, hang or give back the wrong kind of thing, whatever
# arrives. Hypothesis generates thousands of odd inputs (broken text, huge strings, random bytes).
import os, sys, hmac, hashlib, time, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.disable(logging.WARNING)
from hypothesis import given, settings, strategies as st, HealthCheck
import spamguard as sg
from Crypto.Cipher import AES

settings.register_profile("sg", max_examples=400, deadline=2000, derandomize=True,
                          suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large])
settings.load_profile("sg")
ok = fail = 0


def prop(name, fn):
    global ok, fail
    try:
        fn(); ok += 1
    except Exception as e:
        fail += 1
        print("FAIL", name, "-", type(e).__name__, str(e).splitlines()[0][:200] if str(e) else "")


TEXT = st.text(max_size=400)
WILD = st.one_of(st.text(max_size=300),
                 st.text(alphabet=st.characters(min_codepoint=0x1F000, max_codepoint=0x1FAFF), max_size=80),
                 st.text(alphabet="​‍️\U000e0041\U000e007f0123456789 @[]:", max_size=120))


@given(WILD)
def t_text_functions(t):
    n = sg.normalise(t)
    assert isinstance(n, str) and n == n.strip()
    assert isinstance(sg.strip_emoji(t), str)
    assert isinstance(sg.garbage_score(t), int)
    assert isinstance(sg.is_garbage(t), bool)
    assert isinstance(sg.is_obfuscated(t), bool) and isinstance(sg.is_obfuscated(t, True), bool)
    assert isinstance(sg.emoji_tokens(t), list)
    assert isinstance(sg.weighted_len(t), int) and sg.weighted_len(t) >= 0
    assert sg.text_key(t).startswith("text:") and len(sg.text_key(t)) == 15
    assert isinstance(sg.shingles(n), frozenset)
    assert isinstance(sg.name_shape(t), str)


@given(WILD, st.integers(min_value=1, max_value=200))
def t_middle_chunk(t, length):
    c = sg.middle_chunk(t, length)
    assert isinstance(c, str) and len(c) <= max(length, len(t.strip()))
    assert c in t or c == t.strip()


@given(st.lists(WILD, max_size=6), st.integers(min_value=1, max_value=60))
def t_common_text(texts, minimum):
    for r in (sg.common_words(texts, minimum), sg.common_substring(texts, minimum)):
        assert r is None or isinstance(r, (str, list))


PATHISH = st.one_of(st.none(), st.text(max_size=80), st.integers(), st.floats(allow_nan=True),
                    st.lists(st.one_of(st.text(max_size=8), st.integers(), st.none()), max_size=10),
                    st.dictionaries(st.text(max_size=4), st.integers(), max_size=3), st.just("null"), st.just("[1,2"))


@given(PATHISH)
def t_parse_path(v):
    out = sg.parse_path(v)
    assert isinstance(out, list) and all(isinstance(h, str) and h == h.strip() and h == h.upper() for h in out)


@given(st.text(alphabet="0123456789ABCDEFabcdefxX", max_size=10), st.text(alphabet="0123456789ABCDEF", max_size=10))
def t_hops_related(a, b):
    assert sg.hops_related(a, b) == sg.hops_related(b, a)


CH = {"Public": sg.PUBLIC_CHANNEL_KEY}


@given(st.binary(max_size=400))
def t_decrypt_random_bytes(b):
    r = sg.decrypt_group_text(b, CH)
    assert r is None or (isinstance(r, dict) and {"channel", "sender", "text"} <= set(r))


@given(st.binary(max_size=400))
def t_decrypt_right_header_wrong_body(b):
    # A packet that claims the right channel and carries any body: must be rejected cleanly, not crash.
    head = bytes([sg.channel_hash_byte(sg.PUBLIC_CHANNEL_KEY)])
    r = sg.decrypt_group_text(head + b, CH)
    assert r is None or isinstance(r, dict)


def build(sender, text, key=sg.PUBLIC_CHANNEL_KEY):
    k = sg._secret32(key)
    pt = int(time.time()).to_bytes(4, "little") + b"\x00" + f"{sender}: {text}".encode()
    pt += b"\x00" * ((-len(pt)) % 16)
    ct = AES.new(k[:16], AES.MODE_ECB).encrypt(pt)
    return bytes([sg.channel_hash_byte(key)]) + hmac.new(k, ct, hashlib.sha256).digest()[:2] + ct


NAME = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=":"), min_size=1, max_size=20)
BODY = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), min_size=1, max_size=100)


@given(NAME, BODY)
def t_decrypt_round_trip(name, body):
    r = sg.decrypt_group_text(build(name, body), CH)
    assert r is not None, "a genuine message was not read"
    assert r["text"] == body and r["sender"] == name.strip(), (r, name, body)


for name, fn in [("text functions never crash", t_text_functions), ("middle_chunk stays inside the text", t_middle_chunk),
                 ("common words/substring", t_common_text), ("parse_path always gives a clean list", t_parse_path),
                 ("hops_related is symmetric", t_hops_related), ("random bytes never crash the decoder", t_decrypt_random_bytes),
                 ("forged packets are rejected cleanly", t_decrypt_right_header_wrong_body),
                 ("genuine messages round-trip", t_decrypt_round_trip)]:
    prop(name, fn)
print(f"{ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
