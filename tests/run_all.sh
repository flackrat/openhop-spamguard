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
python3 -c "import Crypto" 2>/dev/null || pip install -q pycryptodome 2>/dev/null || pip install -q --break-system-packages pycryptodome
TESTS="scenarios redteam testfloodguard soakfloodguard testwardrive testreplay testinterference testwardrive testnamedflood testfreespeech testforgive testprofiles testknownlist testclearauto testohchannels testlive testfrontend testrepeat testown testautoprotect test59 test5103 test511m testmb testverdict testpub testreset testlearn testknownthen testchannels testgarbage testnames testdocker testplugin testmigrate testpluginops"
[ "${1:-}" = "--slow" ] && TESTS="$TESTS teststress"
if python3 -c "import playwright" 2>/dev/null && command -v npm >/dev/null; then
  [ -d .leaflet/node_modules/leaflet ] || (mkdir -p .leaflet && cd .leaflet && npm i -s leaflet@1.9.4 >/dev/null 2>&1)
  [ -d .axe/node_modules/axe-core ] || (mkdir -p .axe && cd .axe && npm i -s axe-core@4.10.2 >/dev/null 2>&1)
  TESTS="$TESTS testguess testhist testa11y testchpick"
else
  echo "(skipping the browser test: Playwright or npm not available)"
fi
fail=0
for t in $TESTS; do
  out=$(timeout 900 python3 "$t.py" 2>&1); rc=$?
  last=$(echo "$out" | grep -E "passed|^ok$|errors \[|FAIL|Traceback|Error" | tail -3 | tr '\n' ' ')
  if [ $rc -ne 0 ] || echo "$out" | grep -qE "^FAIL|Traceback"; then fail=1; echo "FAIL  $t: $last"; echo "$out" | grep -E "^FAIL|Error" | head -5 | sed 's/^/      /'
  else echo "ok    $t: $last"; fi
done
[ $fail -eq 0 ] && echo "ALL TESTS PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
