#!/usr/bin/env bash
# Runs SpamGuard's test suite against a fake openHop. Nothing here talks to a real repeater.
#   bash tests/run_all.sh          quick suite (about 3 minutes)
#   bash tests/run_all.sh --slow   also the Pi-sized stress test (about 5 more minutes)
# Needs: python3, git, pycryptodome (installed if missing). The browser test needs Playwright
# with Chromium and Node; it is skipped if they aren't there.
set -u
cd "$(dirname "$0")"
OPENHOP_COMMIT=13eb8b2   # openHop version the tests were written against (has the decrypt-cache bug)
if [ ! -d .openhop/repeater ]; then
  git clone -q https://github.com/openhop-dev/openhop_repeater .openhop && git -C .openhop checkout -q "$OPENHOP_COMMIT" \
    || { echo "could not fetch openHop source"; exit 2; }
fi
if [ ! -d .openhop_core/src ]; then
  git clone -q https://github.com/openhop-dev/openhop_core .openhop_core && git -C .openhop_core checkout -q v1.1.3 \
    || { echo "could not fetch openhop_core source"; exit 2; }
fi
if ! python3 -c "import hypothesis, Crypto, nacl, yaml" 2>/dev/null; then
  # Locked, hash-checked versions (requirements/ci.txt).
  pip install -q --require-hashes -r ../requirements/ci.txt 2>/dev/null || pip install -q --break-system-packages --require-hashes -r ../requirements/ci.txt
fi
TESTS="scenarios redteam testrulecap testradio testhashsize testsharedid testmesh testfloodguard soakfloodguard testwardrive testreplay testinterference testnamedflood testfreespeech testforgive testprofiles testknownlist testclearauto testohchannels testlive testfrontend testrepeat testslowrepeat testrulesview testreporting testprivacy testsecrets testown testautoprotect test59 test5103 test511m testmb testverdict testpub testreset testlearn testknownthen testchannels testgarbage testfuzz testnames testdocker testplugin testmigrate testpluginops testupdsh testpreflight testlevel testmapsenders testquarantine testroute testroutesurge testtypesurge testsigned testdamaged testaudit testrandomtail testfgbreakdown testknownage testevasion testsettingsaudit testsignedname teststatebak testvarylimits testbrevity testsbom testforgedhop testidentity testcodeconfidence testresilience testrulesflat testtextsense testopenhopfixed testquickresend testpublicbots testexperimentaloff testadvisor testfixes6271 teststem testautolevel testmachine teststemmem testautoadv testupdverify testinstpw testsymboljunk testfixes6291 testbypass630 testbypass631 testfarcopy testspoofdevice testlookalikecopy testsenderparse testmarks testrobust testupdsafe testmigrated632 testchannelsync testanswers testownership testmatchsame testaudit636 testpeople testspoof testsentences teststarts"
[ "${1:-}" = "--slow" ] && TESTS="$TESTS teststress"
if python3 -c "import playwright" 2>/dev/null && command -v npm >/dev/null; then
  # Locked, integrity-checked versions (tests/npm/*/package-lock.json), linked to where the browser tests look.
  [ -d .leaflet/node_modules/leaflet ] || ( (cd npm/leaflet && npm ci --ignore-scripts -s >/dev/null 2>&1) && ln -sfn npm/leaflet .leaflet )
  [ -d .axe/node_modules/axe-core ] || ( (cd npm/axe && npm ci --ignore-scripts -s >/dev/null 2>&1) && ln -sfn npm/axe .axe )
  TESTS="$TESTS testguess testmappins testupdprog testfgcalm testhist testa11y testchpick testlevelui testmapsendersui testquarantineui testrouteui testfgbreakdownui testlabelui testsensehintui testwebsafety testexpui testmultilabelui testmaptiles testchsyncui testpeopleui testspoofui testtitle"
else
  echo "(skipping the browser test: Playwright or npm not available)"
  # In CI the browser tests are required: a run without them must not report that everything passed.
  [ -n "${CI:-}" ] && BROWSER_MISSING=1
fi
# SG_TEST_PY runs each test another way, e.g. under coverage: SG_TEST_PY="python3 -m coverage run --parallel-mode"
PY=${SG_TEST_PY:-python3}
fail=0
for t in $TESTS; do
  out=$(timeout 900 $PY "$t.py" 2>&1); rc=$?
  last=$(echo "$out" | grep -E "passed|^ok$|errors \[|FAIL|Traceback|Error" | tail -3 | tr '\n' ' ')
  if [ $rc -ne 0 ] || echo "$out" | grep -qE "^FAIL|Traceback"; then fail=1; echo "FAIL  $t: $last"; echo "$out" | grep -E "^FAIL|Error" | head -5 | sed 's/^/      /'
  else echo "ok    $t: $last"; fi
done
if [ -n "${BROWSER_MISSING:-}" ]; then fail=1; echo "FAIL  browser tests: Playwright or npm is missing, so they did not run"; fi
[ $fail -eq 0 ] && echo "ALL TESTS PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
